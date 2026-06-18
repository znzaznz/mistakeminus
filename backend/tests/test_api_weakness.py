"""S7 薄弱点接口测试。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db
from scripts.load_syllabus import DEFAULT_SEED, load_syllabus


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "w.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    load_syllabus(DEFAULT_SEED, conn)
    kp_id = conn.execute(
        "SELECT id FROM knowledge_points WHERE name = '代理制度'"
    ).fetchone()["id"]
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review, knowledge_point_id)
           VALUES (1, '单选', '代理题', ?, ?, '', '[]', 'PDF导入', 0, ?)""",
        (
            json.dumps([{"key": "A", "text": "甲"}]),
            json.dumps(["A"]),
            kp_id,
        ),
    )
    conn.execute(
        "INSERT INTO attempts (question_id, user_answer, is_correct) VALUES (1, '[\"B\"]', 0)"
    )
    conn.execute(
        "INSERT INTO attempts (question_id, user_answer, is_correct) VALUES (1, '[\"A\"]', 1)"
    )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_weakness_list(client):
    items = client.get("/weaknesses").json()
    assert len(items) >= 1
    agent = next(i for i in items if i["name"] == "代理制度")
    assert agent["attempt_count"] == 2
    assert agent["wrong_count"] == 1
    assert agent["accuracy"] == 0.5
    assert agent["priority"] > 0
