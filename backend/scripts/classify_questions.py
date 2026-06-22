"""S6 离线脚本：把真题归类到对应章节的知识点。

用法（backend 目录下）：
    python -m scripts.classify_questions          # 归类未挂知识点的题
    python -m scripts.classify_questions --all    # 全部重归类
    python -m scripts.classify_questions --dry    # 预演不写库
"""

from __future__ import annotations

import sys
from collections import defaultdict

from app import db
from app.classify import (
    format_question_text,
    infer_chapter_from_source,
    keyword_classify,
    plan_classification,
)
from app.llm import classify_question


def _is_jiexi(stem: str) -> bool:
    return "【答案】" in stem or "【解析】" in stem


def get_knowledge_points(conn, chapter: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT k.id, k.name, k.essence
        FROM knowledge_points k
        JOIN exam_points e ON e.id = k.exam_point_id
        WHERE e.chapter = ?
        ORDER BY k.seq
        """,
        (chapter,),
    ).fetchall()
    return [dict(r) for r in rows]


def run(conn, *, all_questions: bool = False, dry: bool = False) -> dict:
    where = "WHERE stem NOT LIKE '%【答案】%' AND stem NOT LIKE '%【解析】%'"
    if not all_questions:
        where += " AND knowledge_point_id IS NULL"
    rows = conn.execute(
        f"SELECT id, stem, options, source_ref FROM questions {where} ORDER BY id"
    ).fetchall()

    by_chapter: dict[str, list] = defaultdict(list)
    unmapped: list = []
    for row in rows:
        if _is_jiexi(row["stem"]):
            continue
        chapter = infer_chapter_from_source(row["source_ref"])
        if chapter:
            by_chapter[chapter].append(row)
        else:
            unmapped.append(row)

    summary = {
        "classified": 0,
        "needs_review": 0,
        "skipped": 0,
        "unmapped": len(unmapped),
        "errors": 0,
    }

    for chapter, chapter_rows in by_chapter.items():
        kps = get_knowledge_points(conn, chapter)
        if not kps:
            summary["errors"] += len(chapter_rows)
            continue
        name_to_id = {k["name"]: k["id"] for k in kps}

        for row in chapter_rows:
            try:
                outcome = keyword_classify(row["stem"], name_to_id)
                if outcome is None:
                    text = format_question_text(row["stem"], row["options"])
                    raw = classify_question(text, kps, subject="经济法", chapter=chapter)
                    outcome = plan_classification(
                        knowledge_point_name=raw["knowledge_point_name"],
                        confidence=raw["confidence"],
                        name_to_id=name_to_id,
                    )
            except Exception:
                summary["errors"] += 1
                if not dry:
                    conn.execute(
                        "UPDATE questions SET needs_review = 1 WHERE id = ?",
                        (row["id"],),
                    )
                continue

            if not dry:
                conn.execute(
                    """
                    UPDATE questions
                    SET knowledge_point_id = ?,
                        needs_review = CASE WHEN ? = 1 THEN 1 ELSE needs_review END
                    WHERE id = ?
                    """,
                    (
                        outcome.knowledge_point_id,
                        1 if outcome.needs_review else 0,
                        row["id"],
                    ),
                )
            summary["classified"] += 1
            if outcome.needs_review:
                summary["needs_review"] += 1

    if unmapped and not dry:
        for row in unmapped:
            conn.execute(
                "UPDATE questions SET needs_review = 1 WHERE id = ?",
                (row["id"],),
            )

    if not dry:
        conn.commit()
    return summary


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    all_q = "--all" in argv
    db.init_db()
    conn = db.get_connection()
    try:
        s = run(conn, all_questions=all_q, dry=dry)
        tag = "[预演]" if dry else "[已写库]"
        print(
            f"{tag} 归类 {s['classified']} 道，"
            f"其中待确认 {s['needs_review']} 道，"
            f"无法推断章节 {s['unmapped']} 道，失败 {s['errors']}。"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
