"""S5 补全预演：打印配对样本供人工抽查（不写库）。

用法：python -m scripts.backfill_preview [--limit 5]
"""

from __future__ import annotations

import json
import sys

from app import db
from app.backfill import QRow, parse_number, plan_backfill


def _is_jiexi(stem: str) -> bool:
    return "【答案】" in stem or "【解析】" in stem


def _pdf_key(source_ref: str | None) -> str:
    return (source_ref or "").split("#")[0]


def _to_qrow(row) -> QRow:
    return QRow(
        id=row["id"],
        number=parse_number(row["stem"]),
        answer=json.loads(row["correct_answer"]),
        explanation=row["explanation"],
    )


def preview(conn, limit: int = 5) -> None:
    rows = conn.execute(
        "SELECT id, stem, source_ref, correct_answer, explanation FROM questions ORDER BY id"
    ).fetchall()
    by_pdf: dict[str, dict[str, list]] = {}
    for r in rows:
        bucket = by_pdf.setdefault(_pdf_key(r["source_ref"]), {"zt": [], "jx": []})
        bucket["jx" if _is_jiexi(r["stem"]) else "zt"].append(r)

    stem_by_id = {r["id"]: r["stem"][:80] for r in rows}

    for pdf, bucket in by_pdf.items():
        zhenti = [_to_qrow(r) for r in bucket["zt"]]
        jiexi = [_to_qrow(r) for r in bucket["jx"]]
        if not zhenti:
            continue
        print(f"\n=== {pdf}  真题 {len(zhenti)} / 解析 {len(jiexi)} ===")
        shown = 0
        for a in plan_backfill(zhenti, jiexi):
            if shown >= limit:
                break
            zt_stem = stem_by_id.get(a.zhenti_id, "?")
            jx_stem = stem_by_id.get(a.jiexi_id, "—") if a.jiexi_id else "—"
            print(
                f"  [{a.note}] review={a.needs_review}\n"
                f"    真题#{a.zhenti_id} 题号{zhenti[[x.id for x in zhenti].index(a.zhenti_id)].number}: {zt_stem}…\n"
                f"    解析#{a.jiexi_id}: {jx_stem}…\n"
                f"    → 答案={a.set_answer}  解析={'有' if a.set_explanation else '无'}"
            )
            shown += 1


def main(argv: list[str]) -> int:
    limit = 5
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = int(argv[i + 1])
    db.init_db()
    conn = db.get_connection()
    try:
        preview(conn, limit=limit)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
