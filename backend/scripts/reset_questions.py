"""清空题库及相关作答/错题数据，保留知识点体系（S5 数据修复用）。

用法（backend 目录下）：
    python -m scripts.reset_questions          # 清 questions/attempts/mistakes + media/questions
    python -m scripts.reset_questions --keep-media   # 只清表，不删配图文件
"""

from __future__ import annotations

import shutil
import sys

from app import db
from app.config import settings


def reset(conn, *, keep_media: bool = False) -> dict:
    n_q = conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
    n_a = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
    n_m = conn.execute("SELECT COUNT(*) c FROM mistakes").fetchone()["c"]
    # 依赖 questions 的表须先清（含 S9 SM-2 / 每日任务 / S10 草稿）
    conn.execute("DELETE FROM daily_task_items")
    conn.execute("DELETE FROM daily_tasks")
    conn.execute("DELETE FROM question_sm2")
    conn.execute("DELETE FROM upload_drafts")
    conn.execute("DELETE FROM mistakes")
    conn.execute("DELETE FROM attempts")
    conn.execute("DELETE FROM questions")
    conn.commit()
    media_removed = False
    media_dir = settings.media_dir / "questions"
    if not keep_media and media_dir.exists():
        shutil.rmtree(media_dir)
        media_removed = True
    return {
        "questions": n_q,
        "attempts": n_a,
        "mistakes": n_m,
        "media_removed": media_removed,
    }


def main(argv: list[str]) -> int:
    keep_media = "--keep-media" in argv
    db.init_db()
    conn = db.get_connection()
    try:
        s = reset(conn, keep_media=keep_media)
        print(
            f"[OK] 已清空 {s['questions']} 道题、{s['attempts']} 条作答、{s['mistakes']} 条错题。"
            f"{' 配图目录已删。' if s['media_removed'] else ''}"
            f"知识点表未动。"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
