"""S9 每日任务 API 测试。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "d.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    for i in range(1, 6):
        conn.execute(
            """INSERT INTO questions
               (id, question_type, stem, options, correct_answer, explanation,
                images, source, needs_review)
               VALUES (?, '单选', ?, ?, ?, '', '[]', 'PDF导入', 0)""",
            (
                i,
                f"题{i}",
                json.dumps([{"key": "A", "text": "甲"}]),
                json.dumps(["A"]),
            ),
        )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app), conn
    app.dependency_overrides.clear()
    conn.close()


def test_daily_task_created(client):
    c, _ = client
    summary = c.get("/daily-task").json()
    assert summary["total"] >= 1
    assert summary["completed"] == 0
    qs = c.get("/daily-task/questions").json()
    assert len(qs) == summary["total"]


def test_attempt_marks_complete(client):
    c, _ = client
    qid = c.get("/daily-task/questions").json()[0]["id"]
    c.post("/attempts", json={"question_id": qid, "user_answer": ["A"]})
    summary = c.get("/daily-task").json()
    assert summary["completed"] == 1


def test_settings_update(client):
    c, _ = client
    c.put("/settings", json={"daily_target_count": 5})
    assert c.get("/settings").json()["daily_target_count"] == 5
