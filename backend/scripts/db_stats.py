"""题库/要义统计（S5 验收用）。

用法：python -m scripts.db_stats
"""

from __future__ import annotations

from app import db


def main() -> int:
    db.init_db()
    conn = db.get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
        jiexi = conn.execute(
            "SELECT COUNT(*) c FROM questions WHERE stem LIKE '%【答案】%' OR stem LIKE '%【解析】%'"
        ).fetchone()["c"]
        practice = conn.execute(
            """
            SELECT COUNT(*) c FROM questions
            WHERE needs_review = 0
              AND stem NOT LIKE '%【答案】%'
              AND stem NOT LIKE '%【解析】%'
              AND NOT (question_type IN ('单选', '多选') AND options = '[]')
            """
        ).fetchone()["c"]
        no_ans = conn.execute(
            "SELECT COUNT(*) c FROM questions WHERE correct_answer = '[]' AND needs_review = 0"
        ).fetchone()["c"]
        has_expl = conn.execute(
            "SELECT COUNT(*) c FROM questions WHERE explanation IS NOT NULL AND explanation != '' AND needs_review = 0"
        ).fetchone()["c"]
        review = conn.execute(
            "SELECT COUNT(*) c FROM questions WHERE needs_review = 1"
        ).fetchone()["c"]
        with_essence = conn.execute(
            "SELECT COUNT(*) c FROM knowledge_points WHERE essence IS NOT NULL AND essence != ''"
        ).fetchone()["c"]
        print(f"questions total={total} practiceable={practice} needs_review={review}")
        print(f"jiexi_left={jiexi} no_answer_clean={no_ans} has_explanation={has_expl}")
        print(f"knowledge_points with_essence={with_essence}/116")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
