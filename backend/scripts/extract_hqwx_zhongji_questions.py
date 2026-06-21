"""Extract HQWX Zhongji exam PDF questions from text layers and import them.

ponytail: narrow one-source parser; replace with a general parser only after a second source needs it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "mistakegenie.db"
PDF_DIR = Path.home() / "Downloads" / "zhongji_kuaiji_pdfs"
OUT_DIR = Path.home() / "Downloads" / "needreadfile_output"
SOURCE = "环球网校中级真题PDF"

SUBJECTS = ("中级会计实务", "财务管理", "经济法")
TYPE_HEADINGS = [
    ("单选题", "单选"),
    ("单项选择题", "单选"),
    ("多选题", "多选"),
    ("多项选择题", "多选"),
    ("判断题", "判断"),
    ("简答题", "简答"),
    ("计算分析题", "计算分析"),
    ("综合题", "综合"),
]
QUESTION_TYPES = {"单选", "多选", "判断"}

NOISE = (
    "咨询热线",
    "微信扫码刷题",
    "免费约直播领资料",
    "免费订阅考试提醒",
    "扫码关注",
    "环球网校移动课堂APP",
    "环球网校侵权必究",
    "初中级会计职称网公众号",
    "本试题是根据考生回忆整理",
)

ANSWER_RE = re.compile(r"(?:【|\[)(?:参考答案|答案)?(?:】|\])\s*([A-DX√×对错正确错误]+)?", re.I)
ANALYSIS_RE = re.compile(r"(?:【|\[)(?:参考解析|解析)(?:】|\])", re.I)
OPTION_MARK_RE = re.compile(r"(?:(?<=\n)|^|(?<=\s))([A-Da-d])(?:[\.\、．]\s*|\s+)")
NUM_START_RE = re.compile(r"(?m)^(?:\d{1,2}[\.、]|[（(]\d{1,2}[）)])\s*")
BRACKET_Q_RE = re.compile(
    r"(?:【|\[)(单选题|单项选择题|多选题|多项选择题|判断题|简答题|计算分析题|综合题)(?:】|\])\s*"
)
TAG_RES = [
    re.compile(r"本题考核[“\"\s]*([^。；;，,]+?)(?:[”\"\s]*知识点)?[。；;，,]"),
    re.compile(r"【知识点】([^。；;，,]+)"),
]


@dataclass
class Question:
    subject: str
    year: str | None
    qtype: str
    stem: str
    options: list[dict[str, str]]
    answer: list[str]
    explanation: str
    source_pdf: str
    page_hint: int | None
    knowledge_point_id: int | None = None
    chapter: str | None = None
    exam_point: str | None = None
    confidence: float = 0.45


def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\r", "\n")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or any(x in line for x in NOISE):
            continue
        lines.append(line)
    return "\n".join(lines)


def subject_from_name(name: str) -> str | None:
    if "财务管理" in name or "中级财务管理" in name:
        return "财务管理"
    if "经济法" in name:
        return "经济法"
    if "会计实务" in name:
        return "中级会计实务"
    return None


def qtype_from_heading(text: str) -> str | None:
    s = text.strip()
    for marker, qtype in TYPE_HEADINGS:
        if marker in s:
            return qtype
    return None


def normalize_answer(value: str | None, qtype: str) -> list[str]:
    if not value:
        return []
    text = value.upper().strip().replace(".", "").replace("。", "")
    text = text.replace("√", "对").replace("×", "错").replace("X", "错")
    if qtype == "判断":
        if "对" in text or "正确" in text:
            return ["对"]
        if "错" in text or "错误" in text:
            return ["错"]
    letters = [c for c in text if c in "ABCD"]
    return letters or [text]


def split_answer(block: str) -> tuple[str, list[str], str]:
    m = ANSWER_RE.search(block)
    if not m:
        return block.strip(), [], ""
    before = block[: m.start()].strip()
    ans = m.group(1) or ""
    after = block[m.end() :].strip()
    a = ANALYSIS_RE.search(after)
    if a:
        explanation = after[a.end() :].strip()
    else:
        explanation = after.strip()
    return before, [ans], explanation


def parse_options(stem_text: str) -> tuple[str, list[dict[str, str]]]:
    matches = list(OPTION_MARK_RE.finditer(stem_text))
    if len(matches) < 2:
        return stem_text.strip(), []
    keys = [m.group(1).upper() for m in matches]
    if keys[0] != "A" or any(k not in "ABCD" for k in keys):
        return stem_text.strip(), []
    stem = stem_text[: matches[0].start()].strip()
    options = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stem_text)
        value = re.sub(r"\s+", " ", stem_text[m.end() : end]).strip()
        if value:
            options.append({"key": m.group(1).upper(), "text": value})
    return stem, options


def split_numbered(section: str) -> list[str]:
    starts = [m.start() for m in NUM_START_RE.finditer(section)]
    if not starts:
        return []
    starts.append(len(section))
    blocks = []
    for i in range(len(starts) - 1):
        block = section[starts[i] : starts[i + 1]]
        block = NUM_START_RE.sub("", block, count=1).strip()
        if block:
            blocks.append(block)
    return blocks


def page_texts(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        return [clean_text(page.get_text("text") or "") for page in doc]
    finally:
        doc.close()


def parse_pdf(pdf_path: Path) -> list[Question]:
    subject = subject_from_name(pdf_path.name)
    if not subject:
        return []
    year_match = re.search(r"20\d{2}", pdf_path.name)
    year = year_match.group(0) if year_match else None
    text = "\n".join(page_texts(pdf_path))
    if "真题考点" in pdf_path.name or "考情分析" in text[:500]:
        return []

    pieces: list[tuple[str, str]] = []
    bracket_matches = list(BRACKET_Q_RE.finditer(text))
    for i, m in enumerate(bracket_matches):
        end = bracket_matches[i + 1].start() if i + 1 < len(bracket_matches) else len(text)
        qtype = qtype_from_heading(m.group(1))
        if qtype in QUESTION_TYPES:
            pieces.append((qtype, text[m.end() : end].strip()))

    current_type: str | None = None
    current: list[str] = []
    for line in text.splitlines():
        heading_type = qtype_from_heading(line)
        looks_like_heading = heading_type and (
            len(line) <= 90
            or line.startswith(("一", "二", "三", "四", "五"))
            or line.startswith(("[", "【"))
        )
        if looks_like_heading:
            if current_type and current:
                for block in split_numbered("\n".join(current)):
                    pieces.append((current_type, block))
            current_type = heading_type if heading_type in QUESTION_TYPES else None
            current = []
        elif current_type:
            current.append(line)
    if current_type and current:
        for block in split_numbered("\n".join(current)):
            pieces.append((current_type, block))

    seen: set[tuple[str, str]] = set()
    deduped = []
    for qtype, block in pieces:
        key = (qtype, re.sub(r"\s+", "", block[:120]))
        if key not in seen:
            deduped.append((qtype, block))
            seen.add(key)
    pieces = deduped

    questions: list[Question] = []
    for qtype, block in pieces:
        if qtype not in QUESTION_TYPES:
            continue
        stem_blob, raw_answer, explanation = split_answer(block)
        stem, options = parse_options(stem_blob)
        answer = normalize_answer(raw_answer[0] if raw_answer else None, qtype)
        stem = re.sub(r"\s+", " ", stem).strip(" ：:;；")
        explanation = re.sub(r"\s+", " ", explanation).strip()
        if len(stem) < 8:
            continue
        if qtype in {"单选", "多选"} and len(options) < 2:
            continue
        confidence = 0.7 if answer and (options or qtype not in {"单选", "多选"}) else 0.5
        questions.append(
            Question(
                subject=subject,
                year=year,
                qtype=qtype,
                stem=stem,
                options=options,
                answer=answer,
                explanation=explanation,
                source_pdf=pdf_path.name,
                page_hint=None,
                confidence=confidence,
            )
        )
    return questions


def load_kps(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    rows = conn.execute(
        """
        SELECT kp.id, kp.name AS kp_name, ep.name AS exam_point, ep.chapter, ep.subject
        FROM knowledge_points kp
        JOIN exam_points ep ON ep.id = kp.exam_point_id
        ORDER BY ep.seq, kp.seq
        """
    ).fetchall()
    out = {s: [] for s in SUBJECTS}
    for row in rows:
        if row["subject"] in out:
            out[row["subject"]].append(row)
    return out


def explicit_tag(explanation: str) -> str | None:
    for pattern in TAG_RES:
        m = pattern.search(explanation or "")
        if not m:
            continue
        tag = m.group(1).strip(" ：:、“”\"")
        # ponytail: reject tags that swallowed the next section; OCR/PDF text sometimes drops newlines.
        if any(x in tag for x in ("一、", "二、", "三、", "四、", "单选", "多选", "判断")):
            return None
        return tag if 2 <= len(tag) <= 40 else None
    return None


def score_tag(tag: str, row: sqlite3.Row) -> int:
    kp = row["kp_name"]
    if tag == kp:
        return 100
    if kp and (tag in kp or kp in tag):
        return 80
    return 0


def attach_kps(conn: sqlite3.Connection, questions: list[Question]) -> None:
    by_subject = load_kps(conn)
    for q in questions:
        tag = explicit_tag(q.explanation)
        if not tag:
            continue
        best = None
        best_score = 0
        for row in by_subject.get(q.subject, []):
            score = score_tag(tag, row)
            if score > best_score:
                best_score, best = score, row
        if best and best_score >= 80:
            q.knowledge_point_id = int(best["id"])
            q.chapter = str(best["chapter"])
            q.exam_point = str(best["exam_point"])
            q.confidence = min(0.9, q.confidence + best_score / 200)


def source_ref(q: Question) -> str:
    digest = hashlib.sha1(f"{q.source_pdf}\n{q.stem}".encode("utf-8")).hexdigest()[:12]
    return f"{q.source_pdf}#{digest}"


def import_questions(conn: sqlite3.Connection, questions: list[Question]) -> dict[str, int]:
    counters = {"inserted": 0, "duplicates": 0}
    for q in questions:
        ref = source_ref(q)
        exists = conn.execute(
            "SELECT 1 FROM questions WHERE source = ? AND source_ref = ?",
            (SOURCE, ref),
        ).fetchone()
        if exists:
            counters["duplicates"] += 1
            continue
        conn.execute(
            """
            INSERT INTO questions
                (chapter, exam_point, question_type, difficulty, year, stem, options,
                 correct_answer, explanation, images, source, source_ref, confidence,
                 needs_review, knowledge_point_id)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, '[]', ?, ?, ?, 1, ?)
            """,
            (
                q.chapter or q.subject,
                q.exam_point or "待映射",
                q.qtype,
                q.year,
                q.stem,
                json.dumps(q.options, ensure_ascii=False),
                json.dumps(q.answer, ensure_ascii=False),
                q.explanation,
                SOURCE,
                ref,
                q.confidence,
                q.knowledge_point_id,
            ),
        )
        counters["inserted"] += 1
    return counters


def backup_db() -> Path:
    dst = DB.with_suffix(f".db.bak-hqwx-zhongji-import-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(DB, dst)
    return dst


def run(pdf_dir: Path, *, dry: bool, replace: bool = False) -> dict:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    all_questions: list[Question] = []
    per_file = []
    for pdf in pdfs:
        questions = parse_pdf(pdf)
        all_questions.extend(questions)
        per_file.append({"file": pdf.name, "questions": len(questions), "subject": subject_from_name(pdf.name)})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        attach_kps(conn, all_questions)
        backup = None
        imported = {"inserted": 0, "duplicates": 0}
        if not dry and all_questions:
            backup = str(backup_db())
            if replace:
                conn.execute("DELETE FROM questions WHERE source = ?", (SOURCE,))
            imported = import_questions(conn, all_questions)
            conn.commit()
    finally:
        conn.close()

    by_subject: dict[str, int] = {}
    by_type: dict[str, int] = {}
    mapped = 0
    for q in all_questions:
        by_subject[q.subject] = by_subject.get(q.subject, 0) + 1
        by_type[q.qtype] = by_type.get(q.qtype, 0) + 1
        mapped += int(q.knowledge_point_id is not None)

    report = {
        "source": SOURCE,
        "dry": dry,
        "pdf_dir": str(pdf_dir),
        "pdfs": len(pdfs),
        "extracted": len(all_questions),
        "mapped": mapped,
        "by_subject": by_subject,
        "by_type": by_type,
        "imported": imported,
        "backup": backup,
        "per_file": per_file,
        "samples": [
            {
                "subject": q.subject,
                "type": q.qtype,
                "year": q.year,
                "stem": q.stem[:160],
                "answer": q.answer,
                "options": q.options[:4],
                "kp": q.knowledge_point_id,
                "pdf": q.source_pdf,
            }
            for q in all_questions[:20]
        ],
    }
    OUT_DIR.mkdir(exist_ok=True)
    name = "_hqwx_zhongji_extract_dry_report.json" if dry else "_hqwx_zhongji_import_report.json"
    (OUT_DIR / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--import", dest="do_import", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    report = run(args.pdf_dir, dry=not args.do_import, replace=args.replace)
    print(json.dumps({k: report[k] for k in ["dry", "pdfs", "extracted", "mapped", "by_subject", "by_type", "imported", "backup"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
