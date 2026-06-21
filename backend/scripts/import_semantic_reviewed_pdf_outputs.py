"""Import only semantically reviewed PDF outputs into SQLite."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app import db
from app.config import settings


ROOT = Path.home() / "Downloads" / "needreadfile_output"
REPORT = ROOT / "_semantic_review_report.json"
IMPORT_REPORT = ROOT / "_import_report.json"
SOURCE = "PDF阿里质检通过"
LECTURE_SOURCE = "PDF讲义阿里质检通过"


def _backup_db() -> Path:
    src = settings.db_path
    dst = src.with_suffix(f".db.bak-pdf-import-{datetime.now():%Y%m%d-%H%M%S}")
    if src.exists():
        shutil.copy2(src, dst)
    return dst


def _json(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _chapter_from_pdf(name: str) -> str | None:
    for chapter in ("总论", "公司法律制度", "合伙企业法律制度", "物权法律制度", "合同法律制度", "金融资产和金融负债"):
        if chapter in name:
            return chapter
    if "客观题集训138003" in name:
        return "物权法律制度"
    if "客观题集训333804" in name:
        return "合同法律制度"
    if "客观题集训710399" in name:
        return "合伙企业法律制度"
    return None


def _lecture_block_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for package_path in sorted(ROOT.glob("*/complete-document-package.json")):
        package = json.loads(package_path.read_text(encoding="utf-8"))
        for block in package.get("lecture_blocks", []):
            bid = f"{package_path.parent.name}:p{block.get('page')}"
            out[bid] = {
                **block,
                "source_pdf": Path(package["source_pdf"]).name,
                "package_dir": package_path.parent,
            }
    return out


def _insert_question(conn, row: dict[str, Any]) -> None:
    q = row["question"]
    source_pdf = row["source_pdf"]
    number = q.get("number") or "?"
    conn.execute(
        """
        INSERT INTO questions
            (chapter, exam_point, question_type, difficulty, year, stem, options,
             correct_answer, explanation, images, source, source_ref,
             confidence, needs_review)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 0)
        """,
        (
            q.get("chapter") or _chapter_from_pdf(source_pdf),
            q.get("exam_point"),
            q.get("question_type"),
            q.get("difficulty"),
            q.get("year"),
            q.get("stem"),
            _json(q.get("options")),
            _json(q.get("correct_answer")),
            q.get("explanation"),
            _json(q.get("images")),
            SOURCE,
            q.get("source_ref") or f"{source_pdf}#q={number}",
        ),
    )


def _insert_lecture(conn, row: dict[str, Any], block: dict[str, Any]) -> None:
    page_image = str(block["package_dir"] / block["page_image"]) if block.get("page_image") else None
    conn.execute(
        """
        INSERT INTO lecture_materials
            (source, source_pdf, page, text, readable_summary, images,
             page_image, status, review_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pass', NULL)
        ON CONFLICT(source, source_pdf, page) DO UPDATE SET
            text = excluded.text,
            readable_summary = excluded.readable_summary,
            images = excluded.images,
            page_image = excluded.page_image,
            status = excluded.status,
            review_reason = excluded.review_reason
        """,
        (
            LECTURE_SOURCE,
            row["source_pdf"],
            row["page"],
            block.get("text") or row.get("text_preview") or "",
            row.get("readable_summary"),
            _json(block.get("images")),
            page_image,
        ),
    )


def run() -> dict[str, Any]:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    lecture_blocks = _lecture_block_map()
    db.init_db()
    backup = _backup_db()
    conn = db.get_connection()
    try:
        conn.execute("DELETE FROM questions WHERE source = ?", (SOURCE,))
        conn.execute("DELETE FROM lecture_materials WHERE source = ?", (LECTURE_SOURCE,))

        q_count = 0
        for row in report.get("questions", []):
            if row.get("status") != "pass":
                continue
            _insert_question(conn, row)
            q_count += 1

        l_count = 0
        for row in report.get("lectures", []):
            if row.get("status") != "pass":
                continue
            block = lecture_blocks.get(str(row.get("id")))
            if not block:
                continue
            _insert_lecture(conn, row, block)
            l_count += 1

        conn.commit()
        return {"questions_imported": q_count, "lectures_imported": l_count, "backup": str(backup)}
    finally:
        conn.close()


def main() -> int:
    result = run()
    IMPORT_REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
