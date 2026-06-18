"""载入官方考纲种子到 exam_points / knowledge_points（S4）。

幂等：重跑不产生重复；已存在的知识点**保留其 essence（要义）**，
只刷新能力要求与顺序，避免覆盖用户已锁定/编辑的要义。

用法（backend 目录下）：
    python -m scripts.load_syllabus            # 用默认种子
    python -m scripts.load_syllabus <path.json>
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from app import db
from app.config import PROJECT_ROOT

DEFAULT_SEED = PROJECT_ROOT / "data" / "syllabus-jingjifa-2026.json"


def load_syllabus(seed_path: Path, conn: sqlite3.Connection) -> dict:
    data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    n_ep = n_kp = 0
    ep_seq = kp_seq = 0
    for chapter in data["chapters"]:
        chap = chapter["name"]
        for section in chapter["sections"]:
            ep_seq += 1
            conn.execute(
                """
                INSERT INTO exam_points (chapter, name, seq) VALUES (?, ?, ?)
                ON CONFLICT(chapter, name) DO UPDATE SET seq = excluded.seq
                """,
                (chap, section["name"], ep_seq),
            )
            ep_id = conn.execute(
                "SELECT id FROM exam_points WHERE chapter = ? AND name = ?",
                (chap, section["name"]),
            ).fetchone()["id"]
            n_ep += 1
            for kp in section["knowledge_points"]:
                kp_seq += 1
                # 保留已有 essence：仅更新能力要求与顺序
                conn.execute(
                    """
                    INSERT INTO knowledge_points
                        (exam_point_id, name, mastery_requirement, essence, seq)
                    VALUES (?, ?, ?, NULL, ?)
                    ON CONFLICT(exam_point_id, name) DO UPDATE SET
                        mastery_requirement = excluded.mastery_requirement,
                        seq = excluded.seq
                    """,
                    (ep_id, kp["name"], kp.get("mastery"), kp_seq),
                )
                n_kp += 1
    conn.commit()
    return {"exam_points": n_ep, "knowledge_points": n_kp}


def main(argv: list[str]) -> int:
    seed = Path(argv[0]) if argv else DEFAULT_SEED
    if not seed.exists():
        print(f"[X] 找不到种子文件: {seed}")
        return 1
    db.init_db()
    conn = db.get_connection()
    try:
        summary = load_syllabus(seed, conn)
        total_kp = conn.execute("SELECT COUNT(*) c FROM knowledge_points").fetchone()["c"]
        total_ep = conn.execute("SELECT COUNT(*) c FROM exam_points").fetchone()["c"]
        with_essence = conn.execute(
            "SELECT COUNT(*) c FROM knowledge_points WHERE essence IS NOT NULL AND essence != ''"
        ).fetchone()["c"]
        print(
            f"[OK] 载入完成：本次处理 {summary['exam_points']} 考点 / "
            f"{summary['knowledge_points']} 知识点。"
            f"库内共 {total_ep} 考点 / {total_kp} 知识点，其中 {with_essence} 个已有要义。"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
