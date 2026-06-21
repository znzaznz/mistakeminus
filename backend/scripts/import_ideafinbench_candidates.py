"""Import mapped IDEAFinBench candidates for accounting/financial management."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app import db
from app.config import settings
from app.extraction.schema import validate_draft


ROOT = Path.home() / "Downloads" / "needreadfile_output"
SPECS = {
    "shiwu": {
        "input": ROOT / "_ideafinbench_accounting_candidate_mapping.json",
        "report": ROOT / "_ideafinbench_accounting_import_report.json",
        "source": "GitHub题源-IDEAFinBench-CPA会计",
    },
    "caiwu": {
        "input": ROOT / "_ideafinbench_financial_management_candidate_mapping.json",
        "report": ROOT / "_ideafinbench_financial_management_import_report.json",
        "source": "GitHub题源-IDEAFinBench-CPA财务成本管理",
    },
}


def _backup_db() -> Path:
    src = settings.db_path
    dst = src.with_suffix(f".db.bak-ideafinbench-import-{datetime.now():%Y%m%d-%H%M%S}")
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


def _confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
            {"q": item.get("question"), "a": item.get("answer"), "url": item.get("source_url")},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"IDEAFinBench:{digest}:{item.get('source_url')}"


def _exists(conn, stem: str, source: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM questions WHERE stem = ? AND source = ? LIMIT 1",
        (stem, source),
    ).fetchone() is not None


def run(subject: str, *, dry: bool, min_confidence: float) -> dict[str, Any]:
    spec = SPECS[subject]
    data = json.loads(spec["input"].read_text(encoding="utf-8"))
    items = data.get("items", [])
    conn = db.get_connection()
    report: dict[str, Any] = {
        "input": str(spec["input"]),
        "source": spec["source"],
        "dry": dry,
        "min_confidence": min_confidence,
        "input_items": len(items),
        "inserted": 0,
        "skipped_unmapped": 0,
        "skipped_low_confidence": 0,
        "skipped_duplicates": 0,
        "errors": [],
        "inserted_ids": [],
    }
    try:
        for item in items:
            kp_id = item.get("knowledge_point_id")
            if not kp_id:
                report["skipped_unmapped"] += 1
                continue
            conf = _confidence(item.get("mapping_confidence"))
            if conf < min_confidence:
                report["skipped_low_confidence"] += 1
                continue
            raw = _draft(item)
            draft, err = validate_draft(raw)
            if draft is None:
                report["errors"].append({"question": item.get("question"), "error": err})
                continue
            if _exists(conn, draft.stem, spec["source"]):
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
                VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, '[]', ?, ?, ?, 1, ?)
                """,
                (
                    item.get("chapter"),
                    item.get("exam_point"),
                    draft.question_type,
                    draft.stem,
                    json.dumps([o.model_dump() for o in draft.options], ensure_ascii=False),
                    json.dumps(draft.correct_answer, ensure_ascii=False),
                    draft.explanation or "",
                    spec["source"],
                    _source_ref(item),
                    conf,
                    int(kp_id),
                ),
            )
            report["inserted"] += 1
            report["inserted_ids"].append(int(cur.lastrowid))
        if not dry:
            conn.commit()
        spec["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=["shiwu", "caiwu", "all"], default="all")
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.65)
    args = parser.parse_args()
    db.init_db()
    backup = None if args.dry else str(_backup_db())
    keys = ["shiwu", "caiwu"] if args.subject == "all" else [args.subject]
    for key in keys:
        result = run(key, dry=args.dry, min_confidence=args.min_confidence)
        result["backup"] = backup
        SPECS[key]["report"].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "subject": key,
                    "backup": backup,
                    "inserted": result["inserted"],
                    "skipped_unmapped": result["skipped_unmapped"],
                    "skipped_low_confidence": result["skipped_low_confidence"],
                    "skipped_duplicates": result["skipped_duplicates"],
                    "errors": len(result["errors"]),
                    "report": str(SPECS[key]["report"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
