"""Quality gate for extracted PDF packages before database import.

The extractor writes a broad "document package". This script is stricter:
only complete, readable, answer-matched questions become direct-import
candidates. Lecture/image-review material is kept out of the practice bank.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.extraction.jixun import parse_jixun_pdf


VALID_TYPES = {"单选", "多选", "判断"}
ANSWER_TOKENS = {"A", "B", "C", "D", "正确", "错误", "对", "错", "√", "×"}


@dataclass
class GateItem:
    source_pdf: str
    kind: str
    pages: int = 0
    package_questions: int = 0
    direct_questions: int = 0
    review_questions: int = 0
    lecture_blocks: int = 0
    content_images: int = 0
    vlm_pages: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)


def _kind(name: str) -> str:
    if "客观题集训" in name:
        return "objective_question_bank"
    if "280619" in name or "569072" in name:
        return "liuqi_question_bank"
    if "周二复识" in name:
        return "image_review_material"
    return "lecture_material"


def _bad_text(text: str) -> bool:
    s = (text or "").strip()
    if len(s) < 8:
        return True
    bad_markers = ["【答案】", "【解析】", "未识别", "无法判断", "看不清", "不完整"]
    if any(x in s for x in bad_markers):
        return True
    # A rough hallucination/mojibake guard: too many replacement/control chars.
    weird = sum(1 for ch in s if ord(ch) < 32 and ch not in "\n\t")
    return weird > 0


def _answer_ok(answer: Any, question_type: str) -> bool:
    if not isinstance(answer, list) or not answer:
        return False
    vals = [str(x).strip() for x in answer if str(x).strip()]
    if not vals:
        return False
    if question_type in {"单选", "多选"}:
        return all(v in {"A", "B", "C", "D"} for v in vals)
    if question_type == "判断":
        return all(v in ANSWER_TOKENS for v in vals)
    return False


def _options_ok(options: Any, question_type: str) -> bool:
    if question_type == "判断":
        return options in ([], None) or (
            isinstance(options, list)
            and all(str(o.get("key", "")).strip() for o in options if isinstance(o, dict))
        )
    if not isinstance(options, list) or len(options) != 4:
        return False
    keys = [str(o.get("key", "")).strip() for o in options if isinstance(o, dict)]
    if keys != ["A", "B", "C", "D"]:
        return False
    return all(str(o.get("text", "")).strip() for o in options if isinstance(o, dict))


def _validate_question(q: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    qtype = str(q.get("question_type") or "")
    stem = str(q.get("stem") or "")
    explanation = str(q.get("explanation") or "")
    if qtype not in VALID_TYPES:
        reasons.append("题型异常")
    if _bad_text(stem):
        reasons.append("题干不可用")
    if _stem_looks_joined(stem):
        reasons.append("题干疑似串页/串选项")
    if not _options_ok(q.get("options"), qtype):
        reasons.append("选项不完整")
    for opt in q.get("options") or []:
        if isinstance(opt, dict) and _option_looks_joined(str(opt.get("text") or "")):
            reasons.append(f"选项{opt.get('key', '')}疑似串页/串表格")
            break
    if not _answer_ok(q.get("correct_answer"), qtype):
        reasons.append("答案不可用")
    if len(explanation.strip()) < 6:
        reasons.append("解析过短")
    if q.get("needs_review"):
        reasons.append(str(q.get("review_reason") or "标记为需人工确认"))
    return reasons


def _stem_looks_joined(stem: str) -> bool:
    s = re.sub(r"\s+", "", stem or "")
    if any(x in s for x in ("参考答案", "答案解析", "第四章参考答案", "第五章参考答案")):
        return True
    if s.endswith(("（", "(", "【")):
        return True
    # Most bank questions end at the blank parentheses. If extra text follows,
    # it is usually pasted option/answer text from PDF extraction order.
    for marker in ("（）。", "(）。", "（）", "( )"):
        pos = s.find(marker)
        if pos >= 0 and len(s) - (pos + len(marker)) > 4:
            return True
    if "有）。" in s or "是）。" in s:
        return True
    return False


def _option_looks_joined(text: str) -> bool:
    s = re.sub(r"\s+", "", text or "")
    if len(s) > 160:
        return True
    joined_markers = (
        "注意事项",
        "法律后果",
        "参考答案",
        "考点",
        "项目分类",
        "强化班",
    )
    return any(x in s for x in joined_markers)


def _sample(q: dict[str, Any], prefix: str = "") -> str:
    answer = "".join(str(x) for x in q.get("correct_answer") or [])
    stem = re.sub(r"\s+", " ", str(q.get("stem") or "")).strip()
    return f"{prefix}{q.get('question_type', '?')} 答案={answer} {stem[:90]}"


def _read_package(out_dir: Path) -> dict[str, Any]:
    return json.loads((out_dir / "complete-document-package.json").read_text(encoding="utf-8"))


def _gate_package(out_dir: Path) -> tuple[GateItem, list[dict[str, Any]], list[dict[str, Any]]]:
    package = _read_package(out_dir)
    pdf = Path(package["source_pdf"])
    summary = package["summary"]
    item = GateItem(
        source_pdf=pdf.name,
        kind=_kind(pdf.name),
        pages=int(summary.get("pages") or 0),
        package_questions=int(summary.get("question_count") or 0),
        lecture_blocks=int(summary.get("lecture_block_count") or 0),
        content_images=int(summary.get("content_image_count") or 0),
        vlm_pages=int(summary.get("vlm_page_count") or 0),
        errors=[f"抽取错误页: {summary.get('error_pages')}"] if summary.get("error_pages") else [],
    )

    direct: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    if item.kind == "liuqi_question_bank":
        for q in package.get("questions", []):
            reasons = _validate_question(q)
            if reasons:
                item.review_questions += 1
                review.append({"source_pdf": pdf.name, "question": q, "reasons": reasons})
            else:
                item.direct_questions += 1
                direct.append({"source_pdf": pdf.name, "question": q})
        item.samples = [_sample(x["question"]) for x in direct[:3]]
    elif item.kind in {"lecture_material", "image_review_material"}:
        empty_text_pages = [
            b.get("page")
            for b in package.get("lecture_blocks", [])
            if len(str(b.get("text") or "").strip()) < 30 and b.get("images")
        ]
        if empty_text_pages:
            item.errors.append(f"有图片但文字少的页需人工看: {empty_text_pages[:12]}")
        item.samples = [
            re.sub(r"\s+", " ", str(b.get("text") or "")).strip()[:120]
            for b in package.get("lecture_blocks", [])[:3]
        ]

    return item, direct, review


def _gate_jixun_pdf(pdf: Path) -> tuple[GateItem, list[dict[str, Any]], list[dict[str, Any]]]:
    report = parse_jixun_pdf(pdf)
    item = GateItem(
        source_pdf=pdf.name,
        kind="objective_question_bank",
        package_questions=report.question_count,
    )
    direct: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    if not report.ok:
        item.errors.append(
            f"专用解析未通过: 题{report.question_count}/答案{report.answer_count}, "
            f"缺答案{report.missing_in_answers[:10]}, 多答案{report.missing_in_questions[:10]}, "
            f"错误{report.errors[:3]}"
        )
        return item, direct, review

    for idx, draft in enumerate(report.drafts, start=1):
        q = draft.model_dump()
        q["number"] = idx
        q["source_ref"] = f"{pdf.name}#q={idx}"
        reasons = _validate_question(q)
        if reasons:
            item.review_questions += 1
            review.append({"source_pdf": pdf.name, "question": q, "reasons": reasons})
        else:
            item.direct_questions += 1
            direct.append({"source_pdf": pdf.name, "question": q})
    item.samples = [_sample(x["question"], prefix=f"#{x['question']['number']} ") for x in direct[:3]]
    return item, direct, review


def _write_markdown(
    path: Path,
    items: list[GateItem],
    direct: list[dict[str, Any]],
    review: list[dict[str, Any]],
) -> None:
    lines = [
        "# PDF 入库前质检报告",
        "",
        f"- 可直接入库题目: {len(direct)}",
        f"- 需要人工确认题目/页: {len(review)}",
        f"- 文件数: {len(items)}",
        "",
        "## 文件结论",
        "",
    ]
    for item in items:
        status = "可入库" if item.direct_questions and not item.errors else "先不入库"
        if item.kind in {"lecture_material", "image_review_material"}:
            status = "作为讲义/图片原料，先不进练习题库"
        lines.append(
            f"### {item.source_pdf}\n"
            f"- 类型: {item.kind}\n"
            f"- 结论: {status}\n"
            f"- 页数/图片/VLM页: {item.pages}/{item.content_images}/{item.vlm_pages}\n"
            f"- 题目: 原包 {item.package_questions}，可直接 {item.direct_questions}，待确认 {item.review_questions}"
        )
        if item.errors:
            lines.append(f"- 风险: {'; '.join(item.errors)}")
        if item.samples:
            lines.append("- 抽样:")
            for s in item.samples[:3]:
                lines.append(f"  - {s}")
        lines.append("")

    if review:
        lines.extend(["## 待确认样例", ""])
        for row in review[:40]:
            q = row["question"]
            lines.append(
                f"- {row['source_pdf']} #{q.get('number', '?')}: "
                f"{'; '.join(row['reasons'])} | {_sample(q)}"
            )
    path.write_text("\n".join(lines), encoding="utf-8")


def run(output_root: Path, source_root: Path) -> dict[str, Any]:
    items: list[GateItem] = []
    direct: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for out_dir in sorted(p for p in output_root.iterdir() if p.is_dir()):
        package = _read_package(out_dir)
        pdf = Path(package["source_pdf"])
        if _kind(pdf.name) == "objective_question_bank":
            item, d, r = _gate_jixun_pdf(pdf)
            item.pages = int(package["summary"].get("pages") or 0)
            item.lecture_blocks = int(package["summary"].get("lecture_block_count") or 0)
            item.content_images = int(package["summary"].get("content_image_count") or 0)
            item.vlm_pages = int(package["summary"].get("vlm_page_count") or 0)
        else:
            item, d, r = _gate_package(out_dir)
        items.append(item)
        direct.extend(d)
        review.extend(r)

    # Pick up objective-question PDFs even if no output package exists.
    seen = {x.source_pdf for x in items if x.kind == "objective_question_bank"}
    for pdf in sorted(source_root.glob("*.pdf")):
        if "客观题集训" not in pdf.name or pdf.name in seen:
            continue
        item, d, r = _gate_jixun_pdf(pdf)
        items.append(item)
        direct.extend(d)
        review.extend(r)

    result = {
        "summary": {
            "files": len(items),
            "direct_questions": len(direct),
            "review_items": len(review),
            "blocked_files": [asdict(x) for x in items if x.errors],
        },
        "files": [asdict(x) for x in items],
        "direct_import_candidates": direct,
        "needs_manual_review": review,
    }
    (output_root / "_quality_gate_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_markdown(output_root / "_quality_gate_report.md", items, direct, review)
    return result


def main() -> int:
    home = Path.home()
    output_root = home / "Downloads" / "needreadfile_output"
    source_root = home / "Downloads" / "needreadfile"
    result = run(output_root, source_root)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
