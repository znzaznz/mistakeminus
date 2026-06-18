"""S8 相似题生成与删除测试。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db
from app.similar import SIMILAR_SOURCE, draft_from_llm, insert_similar_question
from app.extraction.schema import QuestionDraft, Option
from scripts.load_syllabus import DEFAULT_SEED, load_syllabus


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "s.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    load_syllabus(DEFAULT_SEED, conn)
    kp_id = conn.execute(
        "SELECT id FROM knowledge_points WHERE name = '代理制度'"
    ).fetchone()["id"]
    conn.execute(
        "UPDATE knowledge_points SET essence = '代理要义' WHERE id = ?", (kp_id,)
    )
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review, knowledge_point_id)
           VALUES (1, '单选', '原题', ?, ?, '解析', '[]', 'PDF导入', 0, ?)""",
        (
            json.dumps([{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}]),
            json.dumps(["A"]),
            kp_id,
        ),
    )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app), conn, kp_id
    app.dependency_overrides.clear()
    conn.close()


MOCK_SIMILAR = {
    "stem": "新代理题",
    "question_type": "单选",
    "options": [{"key": "A", "text": "对"}, {"key": "B", "text": "错"}],
    "correct_answer": ["A"],
    "explanation": "新解析",
}


def test_draft_from_llm():
    d = draft_from_llm(MOCK_SIMILAR)
    assert d.stem == "新代理题"


def test_insert_and_delete_similar(client):
    _, conn, kp_id = client
    draft = QuestionDraft(
        stem="相似题",
        question_type="单选",
        options=[Option(key="A", text="甲")],
        correct_answer=["A"],
        explanation="解",
    )
    new_id = insert_similar_question(
        conn, draft, knowledge_point_id=kp_id, origin_question_id=1
    )
    row = conn.execute("SELECT source, knowledge_point_id FROM questions WHERE id=?", (new_id,)).fetchone()
    assert row["source"] == SIMILAR_SOURCE
    assert row["knowledge_point_id"] == kp_id


@patch("app.main.generate_similar_question", return_value=MOCK_SIMILAR)
def test_api_create_similar(mock_gen, client):
    c, conn, _ = client
    r = c.post("/questions/1/similar")
    assert r.status_code == 200
    data = r.json()
    assert data["stem"] == "新代理题"
    assert data["source"] == SIMILAR_SOURCE
    assert data["origin_question_id"] == 1
    assert data["cached"] is False
    mock_gen.assert_called_once()
    args, kwargs = mock_gen.call_args
    assert args[2] == "单选"
    assert args[3] == "代理制度"


@patch("app.main.generate_similar_question", return_value=MOCK_SIMILAR)
def test_api_similar_per_origin(mock_gen, client):
    """两道原错题各自绑定不同相似题，互不共用。"""
    c, conn, kp_id = client
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review, knowledge_point_id)
           VALUES (2, '多选', '原题二', ?, ?, '解析', '[]', 'PDF导入', 0, ?)""",
        (
            json.dumps([{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}]),
            json.dumps(["A", "B"]),
            kp_id,
        ),
    )
    conn.commit()
    mock_gen.side_effect = [
        {**MOCK_SIMILAR, "stem": "相似题一"},
        {**MOCK_SIMILAR, "stem": "相似题二", "question_type": "多选", "correct_answer": ["A", "B"]},
    ]
    a = c.post("/questions/1/similar").json()
    b = c.post("/questions/2/similar").json()
    assert a["id"] != b["id"]
    assert a["origin_question_id"] == 1
    assert b["origin_question_id"] == 2
    assert a["stem"] != b["stem"]
    assert c.get("/questions/1/similar").json()["id"] == a["id"]
    assert c.get("/questions/2/similar").json()["id"] == b["id"]


@patch("app.main.generate_similar_question", return_value=MOCK_SIMILAR)
def test_api_similar_cached(mock_gen, client):
    c, _, _ = client
    first = c.post("/questions/1/similar").json()
    mock_gen.assert_called_once()
    r = c.get("/questions/1/similar")
    assert r.status_code == 200
    assert r.json()["id"] == first["id"]
    r2 = c.post("/questions/1/similar")
    assert r2.status_code == 200
    assert r2.json()["id"] == first["id"]
    mock_gen.assert_called_once()


@patch("app.main.generate_similar_question", return_value=MOCK_SIMILAR)
def test_api_similar_regenerate(mock_gen, client):
    c, _, _ = client
    first = c.post("/questions/1/similar").json()
    mock_gen.assert_called_once()
    r = c.post("/questions/1/similar?regenerate=true")
    assert r.status_code == 200
    assert r.json()["id"] != first["id"]
    assert mock_gen.call_count == 2


@patch("app.main.generate_similar_question", return_value=MOCK_SIMILAR)
def test_api_delete_similar_only(mock_gen, client):
    c, _, _ = client
    new_id = c.post("/questions/1/similar").json()["id"]
    assert c.delete(f"/questions/{new_id}").status_code == 200
    assert c.delete("/questions/1").status_code == 404
