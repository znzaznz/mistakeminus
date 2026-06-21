"""题库 / 作答记录的 SQLite 访问层。函数都接收 conn，便于测试注入。"""

from __future__ import annotations

import json
import sqlite3

from .mistakes import MistakeRecord


def get_practice_questions(
    conn: sqlite3.Connection,
    limit: int = 10,
    knowledge_point_id: int | None = None,
) -> list[dict]:
    """取一批题供练习。排除需人工确认的题；随机取样。

    不返回正确答案/解析（避免作答前泄题）。
    """
    params: list = []
    kp_filter = ""
    if knowledge_point_id is not None:
        kp_filter = "AND q.knowledge_point_id = ?"
        params.append(knowledge_point_id)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT q.id, q.stem, q.question_type, q.options, q.images, q.exam_point, q.year,
               q.source,
               k.name AS knowledge_point_name
        FROM questions q
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        WHERE q.needs_review = 0
          AND NOT (q.question_type IN ('单选', '多选') AND q.options = '[]')
          AND q.stem NOT LIKE '%【答案】%'
          AND q.stem NOT LIKE '%【解析】%'
          {kp_filter}
        ORDER BY RANDOM()
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_to_public(r) for r in rows]


def get_question(conn: sqlite3.Connection, question_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM questions WHERE id = ?", (question_id,)
    ).fetchone()


def record_attempt(
    conn: sqlite3.Connection,
    question_id: int,
    user_answer: list[str],
    is_correct: bool,
) -> int:
    cur = conn.execute(
        "INSERT INTO attempts (question_id, user_answer, is_correct) VALUES (?, ?, ?)",
        (question_id, json.dumps(user_answer, ensure_ascii=False), 1 if is_correct else 0),
    )
    conn.commit()
    return cur.lastrowid


def get_mistake(conn: sqlite3.Connection, question_id: int) -> MistakeRecord | None:
    row = conn.execute(
        "SELECT * FROM mistakes WHERE question_id = ?", (question_id,)
    ).fetchone()
    if row is None:
        return None
    return MistakeRecord(
        wrong_answer=json.loads(row["wrong_answer"]),
        correct_answer=json.loads(row["correct_answer"]),
        wrong_count=row["wrong_count"],
        correct_count=row["correct_count"],
        first_wrong_at=row["first_wrong_at"],
        last_attempt_at=row["last_attempt_at"],
        mastery=row["mastery"],
    )


def upsert_mistake(
    conn: sqlite3.Connection, question_id: int, rec: MistakeRecord
) -> None:
    conn.execute(
        """
        INSERT INTO mistakes
            (question_id, wrong_answer, correct_answer, wrong_count,
             correct_count, first_wrong_at, last_attempt_at, mastery)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            wrong_answer    = excluded.wrong_answer,
            correct_answer  = excluded.correct_answer,
            wrong_count     = excluded.wrong_count,
            correct_count   = excluded.correct_count,
            last_attempt_at = excluded.last_attempt_at,
            mastery         = excluded.mastery
        """,
        (
            question_id,
            json.dumps(rec.wrong_answer, ensure_ascii=False),
            json.dumps(rec.correct_answer, ensure_ascii=False),
            rec.wrong_count,
            rec.correct_count,
            rec.first_wrong_at,
            rec.last_attempt_at,
            rec.mastery,
        ),
    )
    conn.commit()


def list_mistakes(
    conn: sqlite3.Connection, *, favorite_only: bool = False
) -> list[dict]:
    """错题本列表：错题记录 + 题目展示信息，按最近作答倒序。"""
    fav_filter = "WHERE m.favorite = 1" if favorite_only else ""
    rows = conn.execute(
        f"""
        SELECT m.question_id, m.wrong_answer, m.correct_answer, m.wrong_count,
               m.correct_count, m.first_wrong_at, m.last_attempt_at, m.mastery,
               m.favorite,
               q.stem, q.question_type, q.exam_point, q.year, q.knowledge_point_id,
               q.images,
               k.name AS knowledge_point_name
        FROM mistakes m
        JOIN questions q ON q.id = m.question_id
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        {fav_filter}
        ORDER BY m.last_attempt_at DESC
        """
    ).fetchall()
    return [
        {
            "question_id": r["question_id"],
            "stem": r["stem"],
            "question_type": r["question_type"],
            "exam_point": r["exam_point"],
            "year": r["year"],
            "knowledge_point_name": r["knowledge_point_name"],
            "images": json.loads(r["images"]) if r["images"] else [],
            "wrong_answer": json.loads(r["wrong_answer"]),
            "correct_answer": json.loads(r["correct_answer"]),
            "wrong_count": r["wrong_count"],
            "correct_count": r["correct_count"],
            "first_wrong_at": r["first_wrong_at"],
            "last_attempt_at": r["last_attempt_at"],
            "mastery": r["mastery"],
            "favorite": bool(r["favorite"]),
        }
        for r in rows
    ]


def toggle_mistake_favorite(conn: sqlite3.Connection, question_id: int) -> bool:
    """切换收藏，返回新状态。"""
    row = conn.execute(
        "SELECT favorite FROM mistakes WHERE question_id = ?", (question_id,)
    ).fetchone()
    if row is None:
        raise KeyError(question_id)
    new_val = 0 if row["favorite"] else 1
    conn.execute(
        "UPDATE mistakes SET favorite = ? WHERE question_id = ?",
        (new_val, question_id),
    )
    conn.commit()
    return bool(new_val)


def list_review_questions(conn: sqlite3.Connection) -> list[dict]:
    """待人工确认队列。"""
    rows = conn.execute(
        """
        SELECT q.id, q.stem, q.question_type, q.exam_point, q.needs_review,
               q.knowledge_point_id, k.name AS knowledge_point_name
        FROM questions q
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        WHERE q.needs_review = 1
        ORDER BY q.id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def set_question_knowledge_point(
    conn: sqlite3.Connection,
    question_id: int,
    knowledge_point_id: int,
    *,
    clear_review: bool = False,
) -> None:
    kp = conn.execute(
        "SELECT id FROM knowledge_points WHERE id = ?", (knowledge_point_id,)
    ).fetchone()
    if kp is None:
        raise KeyError(knowledge_point_id)
    sets = "knowledge_point_id = ?"
    params: list = [knowledge_point_id]
    if clear_review:
        sets += ", needs_review = 0"
    params.append(question_id)
    cur = conn.execute(
        f"UPDATE questions SET {sets} WHERE id = ?",
        params,
    )
    if cur.rowcount == 0:
        raise KeyError(question_id)
    conn.commit()


def get_question_public(conn: sqlite3.Connection, question_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT q.id, q.stem, q.question_type, q.options, q.images, q.exam_point, q.year,
               q.source, k.name AS knowledge_point_name
        FROM questions q
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        WHERE q.id = ?
        """,
        (question_id,),
    ).fetchone()
    return _to_public(row) if row else None


def fetch_kp_attempt_stats(conn: sqlite3.Connection) -> list:
    """按知识点聚合作答与错题数据。"""
    from .weakness import KpStats

    rows = conn.execute(
        """
        SELECT
            k.id AS knowledge_point_id,
            k.name,
            e.chapter,
            k.mastery_requirement,
            COUNT(a.id) AS attempt_count,
            COALESCE(SUM(a.is_correct), 0) AS correct_count,
            COALESCE(SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count,
            MAX(a.created_at) AS last_attempt_at,
            (
                SELECT COUNT(*) FROM mistakes m
                JOIN questions q2 ON q2.id = m.question_id
                WHERE q2.knowledge_point_id = k.id
            ) AS mistake_count
        FROM knowledge_points k
        JOIN exam_points e ON e.id = k.exam_point_id
        LEFT JOIN questions q ON q.knowledge_point_id = k.id
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY k.id
        """
    ).fetchall()
    return [
        KpStats(
            knowledge_point_id=r["knowledge_point_id"],
            name=r["name"],
            chapter=r["chapter"],
            mastery_requirement=r["mastery_requirement"],
            attempt_count=r["attempt_count"] or 0,
            correct_count=r["correct_count"] or 0,
            wrong_count=r["wrong_count"] or 0,
            mistake_count=r["mistake_count"] or 0,
            last_attempt_at=r["last_attempt_at"],
        )
        for r in rows
    ]


def get_knowledge_point(conn: sqlite3.Connection, kp_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT k.id, k.name, k.essence, k.mastery_requirement, e.chapter
        FROM knowledge_points k
        JOIN exam_points e ON e.id = k.exam_point_id
        WHERE k.id = ?
        """,
        (kp_id,),
    ).fetchone()


def count_questions_by_knowledge_point(conn: sqlite3.Connection, kp_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) c FROM questions WHERE knowledge_point_id = ?",
        (kp_id,),
    ).fetchone()["c"]


# ----- S9 设置 / 每日任务 / SM-2 -----


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO schema_meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def get_sm2_state(conn: sqlite3.Connection, question_id: int):
    from .sm2 import Sm2State

    row = conn.execute(
        "SELECT ease, interval_days, repetition, due_date FROM question_sm2 WHERE question_id = ?",
        (question_id,),
    ).fetchone()
    if row is None:
        return Sm2State()
    return Sm2State(
        ease=row["ease"],
        interval_days=row["interval_days"],
        repetition=row["repetition"],
        due_date=row["due_date"],
    )


def upsert_sm2_state(conn: sqlite3.Connection, question_id: int, state) -> None:
    conn.execute(
        """
        INSERT INTO question_sm2 (question_id, ease, interval_days, repetition, due_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            ease = excluded.ease,
            interval_days = excluded.interval_days,
            repetition = excluded.repetition,
            due_date = excluded.due_date
        """,
        (question_id, state.ease, state.interval_days, state.repetition, state.due_date),
    )
    conn.commit()


def _practiceable_filter() -> str:
    return """
        q.needs_review = 0
        AND NOT (q.question_type IN ('单选', '多选') AND q.options = '[]')
        AND q.stem NOT LIKE '%【答案】%'
        AND q.stem NOT LIKE '%【解析】%'
    """


def _fetch_due_question_ids(conn: sqlite3.Connection, today: str) -> list[int]:
    from .daily_task import mastery_weight

    rows = conn.execute(
        f"""
        SELECT q.id, k.mastery_requirement, s.due_date
        FROM questions q
        JOIN question_sm2 s ON s.question_id = q.id
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        WHERE {_practiceable_filter()}
          AND s.due_date IS NOT NULL AND s.due_date <= ?
        """,
        (today,),
    ).fetchall()
    rows = sorted(
        rows,
        key=lambda r: (-mastery_weight(r["mastery_requirement"]), r["due_date"] or "", r["id"]),
    )
    return [r["id"] for r in rows]


def _fetch_new_candidates(conn: sqlite3.Connection, exclude: set[int]) -> list[tuple[int, float]]:
    from .daily_task import mastery_weight

    placeholders = ",".join("?" * len(exclude)) if exclude else "0"
    exclude_clause = f"AND q.id NOT IN ({placeholders})" if exclude else ""
    params: list = list(exclude) if exclude else []
    rows = conn.execute(
        f"""
        SELECT q.id, k.mastery_requirement
        FROM questions q
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        LEFT JOIN attempts a ON a.question_id = q.id
        WHERE {_practiceable_filter()}
          {exclude_clause}
        GROUP BY q.id
        HAVING COUNT(a.id) = 0
        ORDER BY q.id
        """,
        params,
    ).fetchall()
    return [(r["id"], mastery_weight(r["mastery_requirement"])) for r in rows]


def ensure_daily_task(conn: sqlite3.Connection, task_date: str) -> None:
    from .daily_task import generate_task_question_ids

    existing = conn.execute(
        "SELECT task_date FROM daily_tasks WHERE task_date = ?", (task_date,)
    ).fetchone()
    if existing:
        return

    target = int(get_setting(conn, "daily_target_count", "30"))
    due_ids = _fetch_due_question_ids(conn, task_date)
    new_cands = _fetch_new_candidates(conn, set())
    ids = generate_task_question_ids(
        due_ids=due_ids,
        new_candidates=new_cands,
        target=target,
        exclude=set(),
    )
    if not ids:
        # 全新用户：随机取可练题
        rows = conn.execute(
            f"""
            SELECT q.id FROM questions q
            WHERE {_practiceable_filter()}
            ORDER BY RANDOM() LIMIT ?
            """,
            (target,),
        ).fetchall()
        ids = [r["id"] for r in rows]

    conn.execute(
        "INSERT INTO daily_tasks (task_date, target_count) VALUES (?, ?)",
        (task_date, target),
    )
    for seq, qid in enumerate(ids):
        conn.execute(
            """
            INSERT INTO daily_task_items (task_date, question_id, seq, completed)
            VALUES (?, ?, ?, 0)
            """,
            (task_date, qid, seq),
        )
    conn.commit()


def get_daily_task_summary(conn: sqlite3.Connection, task_date: str) -> dict:
    ensure_daily_task(conn, task_date)
    row = conn.execute(
        "SELECT target_count FROM daily_tasks WHERE task_date = ?", (task_date,)
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) c FROM daily_task_items WHERE task_date = ?", (task_date,)
    ).fetchone()["c"]
    done = conn.execute(
        "SELECT COUNT(*) c FROM daily_task_items WHERE task_date = ? AND completed = 1",
        (task_date,),
    ).fetchone()["c"]
    return {
        "task_date": task_date,
        "target_count": row["target_count"],
        "total": total,
        "completed": done,
    }


def get_daily_task_questions(conn: sqlite3.Connection, task_date: str) -> list[dict]:
    ensure_daily_task(conn, task_date)
    rows = conn.execute(
        f"""
        SELECT q.id, q.stem, q.question_type, q.options, q.images, q.exam_point, q.year,
               q.source, k.name AS knowledge_point_name, dti.completed, dti.seq
        FROM daily_task_items dti
        JOIN questions q ON q.id = dti.question_id
        LEFT JOIN knowledge_points k ON k.id = q.knowledge_point_id
        WHERE dti.task_date = ?
        ORDER BY dti.completed ASC, dti.seq ASC
        """,
        (task_date,),
    ).fetchall()
    return [_to_public(r) | {"completed": bool(r["completed"])} for r in rows]


def mark_daily_item_complete(conn: sqlite3.Connection, task_date: str, question_id: int) -> None:
    conn.execute(
        """
        UPDATE daily_task_items SET completed = 1
        WHERE task_date = ? AND question_id = ?
        """,
        (task_date, question_id),
    )
    conn.commit()


def list_knowledge_points_brief(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT k.id, k.name, e.subject, e.chapter, k.mastery_requirement
        FROM knowledge_points k
        JOIN exam_points e ON e.id = k.exam_point_id
        ORDER BY e.subject, k.seq
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_taxonomy(conn: sqlite3.Connection) -> list[dict]:
    """知识点体系：章 → 考点 → 知识点，含能力要求、要义、挂题数。"""
    eps = conn.execute(
        "SELECT id, subject, chapter, name FROM exam_points ORDER BY subject, seq"
    ).fetchall()
    kp_rows = conn.execute(
        """
        SELECT k.id, k.exam_point_id, k.name, k.mastery_requirement, k.essence,
               (SELECT COUNT(*) FROM questions q WHERE q.knowledge_point_id = k.id) AS question_count
        FROM knowledge_points k
        ORDER BY k.seq
        """
    ).fetchall()
    kps_by_ep: dict[int, list[dict]] = {}
    for r in kp_rows:
        kps_by_ep.setdefault(r["exam_point_id"], []).append(
            {
                "id": r["id"],
                "name": r["name"],
                "mastery_requirement": r["mastery_requirement"],
                "essence": r["essence"],
                "question_count": r["question_count"],
                "has_essence": bool(r["essence"]),
            }
        )

    chapters: dict[tuple, dict] = {}
    for ep in eps:
        # 按 (科目, 章) 分组：三科可能共用同名章（如"总论"），不能只按章名合并
        key = (ep["subject"], ep["chapter"])
        chap = chapters.setdefault(
            key, {"subject": ep["subject"], "chapter": ep["chapter"], "exam_points": []}
        )
        chap["exam_points"].append(
            {
                "id": ep["id"],
                "name": ep["name"],
                "knowledge_points": kps_by_ep.get(ep["id"], []),
            }
        )
    return list(chapters.values())


def _to_public(row: sqlite3.Row) -> dict:
    """题库行 → 给前端的公开结构（不含答案/解析）。"""
    return {
        "id": row["id"],
        "stem": row["stem"],
        "question_type": row["question_type"],
        "options": json.loads(row["options"]),
        "images": json.loads(row["images"]),
        "exam_point": row["exam_point"],
        "year": row["year"],
        "knowledge_point_name": row["knowledge_point_name"] if "knowledge_point_name" in row.keys() else None,
        "source": row["source"] if "source" in row.keys() else None,
    }
