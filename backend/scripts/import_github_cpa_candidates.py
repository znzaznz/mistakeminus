"""Import mapped GitHub CPA economic-law candidates into the question bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app import db
from app.config import settings
from app.extraction.schema import validate_draft


ROOT = Path.home() / "Downloads" / "needreadfile_output"
INPUT = ROOT / "_github_cpa_economic_law_candidate_mapping.json"
REPORT = ROOT / "_github_cpa_economic_law_import_report.json"
SOURCE = "GitHub题源-IDEAFinBench-CPA经济法"


def _backup_db() -> Path:
    src = settings.db_path
    dst = src.with_suffix(f".db.bak-github-cpa-import-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(src, dst)
    return dst


def _answer(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip().upper() for x in value if str(x).strip()]
    text = str(value or "").strip().upper()
    if not text:
        return []
    if "," in text:
        return [x.strip() for x in text.split(",") if x.strip()]
    if all(c in "ABCD" for c in text):
        return list(text)
    return [text]


def _draft(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "stem": str(item["question"]).strip(),
        "question_type": item["question_type"],
        "options": [
            {"key": key, "text": str(item.get(key) or "").strip()}
            for key in ["A", "B", "C", "D"]
            if str(item.get(key) or "").strip()
        ],
        "correct_answer": _answer(item.get("answer")),
        "explanation": str(item.get("explanation") or "").strip(),
    }


def _source_ref(item: dict[str, Any]) -> str:
    digest = hashlib.sha1(
        json.dumps(
            {
                "q": item.get("question"),
                "a": item.get("answer"),
                "url": item.get("source_url"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"IDEAFinBench:{digest}:{item.get('source_url')}"


def _exists(conn: sqlite3.Connection, stem: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM questions WHERE stem = ? AND source = ? LIMIT 1",
        (stem, SOURCE),
    ).fetchone()
    return row is not None


def run(*, dry: bool) -> dict[str, Any]:
    db.init_db()
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    items = data.get("items", [])
    conn = db.get_connection()
    backup = None if dry else str(_backup_db())
    report: dict[str, Any] = {
        "input": str(INPUT),
        "source": SOURCE,
        "dry": dry,
        "backup": backup,
        "input_items": len(items),
        "inserted": 0,
        "skipped_duplicates": 0,
        "errors": [],
        "inserted_ids": [],
    }
    try:
        for item in items:
            raw = _draft(item)
            draft, err = validate_draft(raw)
            if draft is None:
                report["errors"].append(
                    {
                        "knowledge_point_id": item.get("knowledge_point_id"),
                        "question": item.get("question"),
                        "error": err,
                    }
                )
                continue
            if _exists(conn, draft.stem):
                report["skipped_duplicates"] += 1
                continue
            if dry:
                report["inserted"] += 1
                report["inserted_ids"].append(None)
                continue
            cur = conn.execute(
                """
                INSERT INTO questions
                    (chapter, exam_point, question_type, difficulty, year, stem,
                     options, correct_answer, explanation, images, source,
                     source_ref, confidence, needs_review, knowledge_point_id)
                VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, '[]', ?, ?, 0.82, 1, ?)
                """,
                (
                    item.get("chapter"),
                    item.get("exam_point"),
                    draft.question_type,
                    draft.stem,
                    json.dumps([o.model_dump() for o in draft.options], ensure_ascii=False),
                    json.dumps(draft.correct_answer, ensure_ascii=False),
                    draft.explanation or "",
                    SOURCE,
                    _source_ref(item),
                    item.get("knowledge_point_id"),
                ),
            )
            report["inserted"] += 1
            report["inserted_ids"].append(int(cur.lastrowid))
        if not dry:
            conn.commit()
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    result = run(dry=args.dry)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
