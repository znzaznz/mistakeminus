"""Export local SQLite content to git-trackable JSONL snapshots."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from app import db
from app.config import PROJECT_ROOT


OUT = PROJECT_ROOT / "data" / "imports"
EXTERNAL = Path.home() / "Downloads" / "needreadfile_output"
REPORTS = [
    "_question_knowledge_point_mapping_report.json",
    "_github_cpa_economic_law_candidate_mapping.json",
    "_github_cpa_economic_law_import_report.json",
    "_ideafinbench_accounting_candidate_mapping.json",
    "_ideafinbench_financial_management_candidate_mapping.json",
    "_ideafinbench_accounting_import_report.json",
    "_ideafinbench_financial_management_import_report.json",
]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _rows(table: str) -> list[dict]:
    conn = db.get_connection()
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
    finally:
        conn.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    copied_reports = []
    for table in ["exam_points", "knowledge_points", "questions", "lecture_materials"]:
        rows = _rows(table)
        _write_jsonl(OUT / f"{table}.jsonl", rows)
        print(f"{table}: {len(rows)}")

    reports_dir = OUT / "reports"
    reports_dir.mkdir(exist_ok=True)
    for name in REPORTS:
        src = EXTERNAL / name
        if src.exists():
            shutil.copy2(src, reports_dir / name)
            copied_reports.append(name)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tables": {
            table: len(_rows(table))
            for table in ["exam_points", "knowledge_points", "questions", "lecture_materials"]
        },
        "copied_reports": copied_reports,
        "note": "SQLite is ignored by git; these files are the portable data snapshot.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
