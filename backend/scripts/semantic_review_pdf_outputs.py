"""Remote semantic review for PDF extraction outputs.

Uses DashScope text/VL models as a second pass before import. The goal is not
to beautify text; it is to keep unreadable, joined, hallucinated, or incomplete
items out of the database.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings


ROOT = Path.home() / "Downloads" / "needreadfile_output"
TEXT_CACHE = ROOT / "_semantic_question_review.jsonl"
LECTURE_CACHE = ROOT / "_semantic_lecture_review.jsonl"
REPORT_JSON = ROOT / "_semantic_review_report.json"
REPORT_MD = ROOT / "_semantic_review_report.md"


def _client() -> OpenAI:
    if not settings.dashscope_api_key.strip():
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)


def _json_from_text(text: str) -> Any:
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = min([i for i in [s.find("{"), s.find("[")] if i >= 0], default=-1)
        if start < 0:
            raise
        return json.JSONDecoder().raw_decode(s[start:])[0]


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[str(row["id"])] = row
    return out


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _text_call(client: OpenAI, prompt: str) -> Any:
    resp = client.chat.completions.create(
        model=settings.qwen_text_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是严谨的题库/讲义入库质检员。只判断材料是否可读、是否结构正确、"
                    "是否疑似串页/粘连/缺失/胡编。必须输出严格 JSON。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return _json_from_text(resp.choices[0].message.content or "")


def _vl_call(client: OpenAI, prompt: str, image_path: Path) -> Any:
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    resp = client.chat.completions.create(
        model=settings.qwen_vl_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是严谨的 PDF 页面质检和 OCR 助手。只根据图片可见内容判断，不要补写看不见的内容。"
                    "必须输出严格 JSON。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            },
        ],
        temperature=0,
    )
    return _json_from_text(resp.choices[0].message.content or "")


def _question_payload(row: dict[str, Any]) -> dict[str, Any]:
    q = row["question"]
    return {
        "id": row["id"],
        "source_pdf": row["source_pdf"],
        "number": q.get("number"),
        "question_type": q.get("question_type"),
        "stem": q.get("stem"),
        "options": q.get("options"),
        "correct_answer": q.get("correct_answer"),
        "explanation": q.get("explanation"),
    }


def _review_questions(client: OpenAI, candidates: list[dict[str, Any]], limit: int | None) -> dict[str, dict[str, Any]]:
    cached = _load_jsonl(TEXT_CACHE)
    todo = [x for x in candidates if str(x["id"]) not in cached]
    if limit:
        todo = todo[:limit]

    for i in range(0, len(todo), 8):
        batch = todo[i : i + 8]
        payload = [_question_payload(x) for x in batch]
        prompt = (
            "逐条检查下面题目能不能直接入库练习。判定标准：\n"
            "1. 题干语义完整，没有把选项、参考答案、讲义表格、下一题粘进去。\n"
            "2. 单选/多选必须有 A-D 四个选项，选项文字完整且不串页。\n"
            "3. 答案与题型匹配，多选答案不能超出 A-D。\n"
            "4. 解析读得通，不能明显缺半句或胡编。\n"
            "输出 JSON 数组，每项格式："
            "{\"id\":\"...\",\"status\":\"pass|review|reject\",\"reason\":\"简短中文原因\",\"fixed\":null}。\n"
            "如果只是轻微换行/空格问题仍 pass；如果需要人工看原 PDF 用 review；明显不可用用 reject。\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            data = _text_call(client, prompt)
            rows = data if isinstance(data, list) else data.get("items", [])
            normalized = []
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    continue
                row["id"] = str(row["id"])
                row.setdefault("status", "review")
                row.setdefault("reason", "模型未给出原因")
                normalized.append(row)
            _append_jsonl(TEXT_CACHE, normalized)
            cached.update({str(x["id"]): x for x in normalized})
            print(f"question review {min(i + len(batch), len(todo))}/{len(todo)}")
        except Exception as e:
            fallback = [
                {
                    "id": str(x["id"]),
                    "status": "review",
                    "reason": f"远端质检失败: {e}",
                    "fixed": None,
                }
                for x in batch
            ]
            _append_jsonl(TEXT_CACHE, fallback)
            cached.update({x["id"]: x for x in fallback})
        time.sleep(0.2)
    return cached


def _lecture_blocks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package_path in sorted(ROOT.glob("*/complete-document-package.json")):
        package = json.loads(package_path.read_text(encoding="utf-8"))
        source_pdf = Path(package["source_pdf"]).name
        for block in package.get("lecture_blocks", []):
            text = re.sub(r"\s+", " ", str(block.get("text") or "")).strip()
            rows.append(
                {
                    "id": f"{package_path.parent.name}:p{block.get('page')}",
                    "source_pdf": source_pdf,
                    "page": block.get("page"),
                    "text": text,
                    "images": block.get("images") or [],
                    "page_image": package_path.parent / str(block.get("page_image") or ""),
                }
            )
    return rows


def _review_lecture_text(client: OpenAI, blocks: list[dict[str, Any]], limit: int | None) -> dict[str, dict[str, Any]]:
    cached = _load_jsonl(LECTURE_CACHE)
    todo = [x for x in blocks if str(x["id"]) not in cached]
    if limit:
        todo = todo[:limit]

    text_blocks = [x for x in todo if len(x["text"]) >= 80]
    image_blocks = [x for x in todo if len(x["text"]) < 80]

    for i in range(0, len(text_blocks), 6):
        batch = text_blocks[i : i + 6]
        payload = [
            {
                "id": x["id"],
                "source_pdf": x["source_pdf"],
                "page": x["page"],
                "text": x["text"][:1800],
            }
            for x in batch
        ]
        prompt = (
            "逐页检查讲义文字是否能入库作为知识点材料。标准：\n"
            "1. 文字应当是可读中文，不是乱码。\n"
            "2. 不能明显只有页眉页脚或目录残片。\n"
            "3. 允许包含例题，但整体必须连贯；若疑似缺大段图片文字，标 review。\n"
            "输出 JSON 数组，每项格式："
            "{\"id\":\"...\",\"status\":\"pass|review|reject\",\"reason\":\"简短中文原因\",\"readable_summary\":\"一句话概括本页内容\"}。\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            data = _text_call(client, prompt)
            rows = data if isinstance(data, list) else data.get("items", [])
            normalized = []
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    continue
                row["id"] = str(row["id"])
                row.setdefault("status", "review")
                row.setdefault("reason", "模型未给出原因")
                normalized.append(row)
            _append_jsonl(LECTURE_CACHE, normalized)
            cached.update({str(x["id"]): x for x in normalized})
            print(f"lecture text review {min(i + len(batch), len(text_blocks))}/{len(text_blocks)}")
        except Exception as e:
            fallback = [
                {
                    "id": str(x["id"]),
                    "status": "review",
                    "reason": f"远端文本质检失败: {e}",
                    "readable_summary": "",
                }
                for x in batch
            ]
            _append_jsonl(LECTURE_CACHE, fallback)
            cached.update({x["id"]: x for x in fallback})
        time.sleep(0.2)

    for i, block in enumerate(image_blocks, start=1):
        image_path = Path(block["page_image"])
        if not image_path.exists():
            row = {
                "id": str(block["id"]),
                "status": "review",
                "reason": "页图不存在，无法视觉质检",
                "readable_summary": "",
            }
        else:
            prompt = (
                "检查这页 PDF 图片是否能作为讲义材料入库。请读取可见文字，判断是否完整可读。"
                "输出 JSON：{\"id\":\"%s\",\"status\":\"pass|review|reject\","
                "\"reason\":\"简短中文原因\",\"readable_summary\":\"一句话概括\","
                "\"ocr_text\":\"本页主要可见文字，最多800字\"}。"
                "如果只有页眉/章节标题、没有正文，status=review。不要补写看不见的内容。"
            ) % block["id"]
            try:
                row = _vl_call(client, prompt, image_path)
                if not isinstance(row, dict):
                    row = {"id": str(block["id"]), "status": "review", "reason": "视觉模型返回格式异常"}
                row["id"] = str(block["id"])
                row.setdefault("status", "review")
                row.setdefault("reason", "模型未给出原因")
            except Exception as e:
                row = {
                    "id": str(block["id"]),
                    "status": "review",
                    "reason": f"远端视觉质检失败: {e}",
                    "readable_summary": "",
                }
        _append_jsonl(LECTURE_CACHE, [row])
        cached[str(row["id"])] = row
        print(f"lecture image review {i}/{len(image_blocks)}")
        time.sleep(0.2)

    return cached


def _prepare_candidates() -> list[dict[str, Any]]:
    qgate = json.loads((ROOT / "_quality_gate_report.json").read_text(encoding="utf-8"))
    candidates = []
    for idx, row in enumerate(qgate["direct_import_candidates"], start=1):
        copied = dict(row)
        copied["id"] = f"q{idx}"
        candidates.append(copied)
    return candidates


def _write_report(
    candidates: list[dict[str, Any]],
    q_reviews: dict[str, dict[str, Any]],
    blocks: list[dict[str, Any]],
    l_reviews: dict[str, dict[str, Any]],
) -> None:
    q_by_id = {x["id"]: x for x in candidates}
    question_rows = []
    for qid, review in q_reviews.items():
        if qid in q_by_id:
            question_rows.append({**review, "source_pdf": q_by_id[qid]["source_pdf"], "question": q_by_id[qid]["question"]})

    block_by_id = {str(x["id"]): x for x in blocks}
    lecture_rows = []
    for bid, review in l_reviews.items():
        if bid in block_by_id:
            b = block_by_id[bid]
            lecture_rows.append({**review, "source_pdf": b["source_pdf"], "page": b["page"], "text_preview": b["text"][:300]})

    result = {
        "summary": {
            "question_pass": sum(x.get("status") == "pass" for x in question_rows),
            "question_review": sum(x.get("status") == "review" for x in question_rows),
            "question_reject": sum(x.get("status") == "reject" for x in question_rows),
            "lecture_pass": sum(x.get("status") == "pass" for x in lecture_rows),
            "lecture_review": sum(x.get("status") == "review" for x in lecture_rows),
            "lecture_reject": sum(x.get("status") == "reject" for x in lecture_rows),
        },
        "questions": question_rows,
        "lectures": lecture_rows,
    }
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 阿里远端语义质检报告", "", json.dumps(result["summary"], ensure_ascii=False), ""]
    lines.append("## 题目需处理")
    for row in question_rows:
        if row.get("status") == "pass":
            continue
        q = row["question"]
        lines.append(
            f"- {row['status']} | {row['source_pdf']} #{q.get('number')}: "
            f"{row.get('reason')} | {str(q.get('stem') or '')[:100]}"
        )
    lines.append("")
    lines.append("## 讲义需处理")
    for row in lecture_rows:
        if row.get("status") == "pass":
            continue
        lines.append(
            f"- {row['status']} | {row['source_pdf']} p{row.get('page')}: "
            f"{row.get('reason')} | {row.get('readable_summary', '')[:120]}"
        )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-questions", type=int)
    parser.add_argument("--limit-lectures", type=int)
    args = parser.parse_args()

    client = _client()
    candidates = _prepare_candidates()
    q_reviews = _review_questions(client, candidates, args.limit_questions)
    blocks = _lecture_blocks()
    l_reviews = _review_lecture_text(client, blocks, args.limit_lectures)
    _write_report(candidates, q_reviews, blocks, l_reviews)
    print(REPORT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
