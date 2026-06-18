"""S5 离线脚本：把解析页的答案+解析配对回真题。

用法（backend 目录下）：
    python -m scripts.backfill_answers          # 应用
    python -m scripts.backfill_answers --dry    # 只看计划不写库
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


def run(conn, dry: bool = False) -> dict:
    rows = conn.execute(
        "SELECT id, stem, source_ref, correct_answer, explanation FROM questions ORDER BY id"
    ).fetchall()

    by_pdf: dict[str, dict[str, list]] = {}
    for r in rows:
        bucket = by_pdf.setdefault(_pdf_key(r["source_ref"]), {"zt": [], "jx": []})
        bucket["jx" if _is_jiexi(r["stem"]) else "zt"].append(r)

    summary = {"backfilled": 0, "needs_review": 0, "jiexi_removed": 0, "unmatched": 0}
    for pdf, bucket in by_pdf.items():
        zhenti = [_to_qrow(r) for r in bucket["zt"]]
        jiexi = [_to_qrow(r) for r in bucket["jx"]]
        if not zhenti:
            continue
        for a in plan_backfill(zhenti, jiexi):
            if a.jiexi_id is None:
                summary["unmatched"] += 1
            sets, params = [], []
            if a.set_answer is not None:
                sets.append("correct_answer = ?")
                params.append(json.dumps(a.set_answer, ensure_ascii=False))
            if a.set_explanation is not None:
                sets.append("explanation = ?")
                params.append(a.set_explanation)
            if a.needs_review:
                sets.append("needs_review = 1")
                summary["needs_review"] += 1
            else:
                summary["backfilled"] += 1
            if sets and not dry:
                conn.execute(
                    f"UPDATE questions SET {', '.join(sets)} WHERE id = ?",
                    params + [a.zhenti_id],
                )
            # 高置信匹配：解析内容已并入真题 → 移出题库
            if a.jiexi_id is not None and not a.needs_review:
                summary["jiexi_removed"] += 1
                if not dry:
                    conn.execute("DELETE FROM questions WHERE id = ?", (a.jiexi_id,))
    if not dry:
        conn.commit()
    return summary


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    db.init_db()
    conn = db.get_connection()
    try:
        s = run(conn, dry=dry)
        tag = "[预演]" if dry else "[已写库]"
        print(
            f"{tag} 补全 {s['backfilled']} 道（删解析 {s['jiexi_removed']} 条），"
            f"待人工确认 {s['needs_review']} 道，未配到解析 {s['unmatched']} 道。"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
