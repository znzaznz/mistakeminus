"""S10 截图上传测试。"""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.main import app, get_db
from app.uploads import confirm_upload, draft_from_confirm_body, insert_draft, save_upload_image
from app.extraction.schema import QuestionDraft, Option


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "u.db"
    media = tmp_path / "media"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    settings.media_dir = media
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app), conn, media
    app.dependency_overrides.clear()
    conn.close()


MOCK_VLM = [{
    "stem": "上传题",
    "question_type": "单选",
    "options": [{"key": "A", "text": "对"}, {"key": "B", "text": "错"}],
    "correct_answer": ["A"],
    "explanation": "解析",
    "confidence": 0.9,
}]


def test_save_upload_image(tmp_path):
    p = save_upload_image(b"png", tmp_path)
    assert (tmp_path / p).exists()


def test_draft_from_confirm():
    d = draft_from_confirm_body({
        "stem": "题",
        "question_type": "单选",
        "options": [{"key": "A", "text": "甲"}],
        "correct_answer": ["A"],
    })
    assert d.stem == "题"


@patch("app.main.vlm.extract_questions", return_value=MOCK_VLM)
def test_upload_api(mock_vlm, client):
    c, conn, _ = client
    r = c.post(
        "/uploads",
        files={"file": ("t.png", BytesIO(b"fake"), "image/png")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["stem"] == "上传题"
    assert data["id"]


@patch("app.main.vlm.extract_questions", return_value=MOCK_VLM)
def test_confirm_upload(mock_vlm, client):
    c, conn, media = client
    draft_id = c.post(
        "/uploads",
        files={"file": ("t.png", BytesIO(b"fake"), "image/png")},
    ).json()["id"]
    r = c.post(
        f"/uploads/{draft_id}/confirm",
        json={
            "stem": "确认题",
            "question_type": "单选",
            "options": [{"key": "A", "text": "甲"}],
            "correct_answer": ["A"],
            "explanation": "解",
        },
    )
    assert r.status_code == 200
    qid = r.json()["question_id"]
    mistakes = c.get("/mistakes").json()
    assert any(m["question_id"] == qid for m in mistakes)
