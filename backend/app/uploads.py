"""S10 截图上传识题：草稿确认入库。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .extraction.schema import QuestionDraft, validate_draft
from .mistakes import MistakeRecord

UPLOAD_SOURCE = "截图上传"


def save_upload_image(data: bytes, media_dir: Path, suffix: str = ".png") -> str:
    """存上传原图，返回相对 media_dir 的路径。"""
    sub = Path("uploads")
    (media_dir / sub).mkdir(parents=True, exist_ok=True)
    rel = sub / f"{uuid.uuid4().hex}{suffix}"
    (media_dir / rel).write_bytes(data)
    return rel.as_posix()


def insert_draft(conn: sqlite3.Connection, image_path: str, raw: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO upload_drafts (image_path, draft_json, confidence)
        VALUES (?, ?, ?)
        """,
        (
            image_path,
            json.dumps(raw, ensure_ascii=False),
            float(raw.get("confidence", 0.5)),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_draft(conn: sqlite3.Connection, draft_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, image_path, draft_json, confidence FROM upload_drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if row is None:
        return None
    draft = json.loads(row["draft_json"])
    return {
        "id": row["id"],
        "image_path": row["image_path"],
        "confidence": row["confidence"],
        **draft,
    }


def confirm_upload(
    conn: sqlite3.Connection,
    draft_id: int,
    draft: QuestionDraft,
    *,
    knowledge_point_id: int | None,
    image_path: str,
    now: str,
) -> int:
    """确认草稿入库并写入错题本，返回新题 id。"""
    cur = conn.execute(
        """
        INSERT INTO questions
            (chapter, exam_point, question_type, difficulty, year, stem,
             options, correct_answer, explanation, images, source, source_ref,
             confidence, needs_review, knowledge_point_id)
        VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            draft.chapter,
            draft.exam_point,
            draft.question_type,
            draft.difficulty,
            draft.stem,
            json.dumps([o.model_dump() for o in draft.options], ensure_ascii=False),
            json.dumps(draft.correct_answer, ensure_ascii=False),
            draft.explanation or "",
            json.dumps([image_path], ensure_ascii=False),
            UPLOAD_SOURCE,
            f"upload_draft:{draft_id}",
            draft.confidence,
            knowledge_point_id,
        ),
    )
    qid = cur.lastrowid
    rec = MistakeRecord(
        wrong_answer=[],
        correct_answer=draft.correct_answer,
        wrong_count=1,
        correct_count=0,
        first_wrong_at=now,
        last_attempt_at=now,
        mastery="未掌握",
    )
    conn.execute(
        """
        INSERT INTO mistakes
            (question_id, wrong_answer, correct_answer, wrong_count,
             correct_count, first_wrong_at, last_attempt_at, mastery, favorite)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            qid,
            json.dumps(rec.wrong_answer, ensure_ascii=False),
            json.dumps(rec.correct_answer, ensure_ascii=False),
            rec.wrong_count,
            rec.correct_count,
            rec.first_wrong_at,
            rec.last_attempt_at,
            rec.mastery,
        ),
    )
    conn.execute("DELETE FROM upload_drafts WHERE id = ?", (draft_id,))
    conn.commit()
    return qid


def draft_from_confirm_body(body: dict) -> QuestionDraft:
    d, err = validate_draft(body)
    if d is None:
        raise ValueError(err)
    return d
