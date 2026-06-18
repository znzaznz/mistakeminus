"""S3 错题本接口/集成测试：答错→自动进本→列表可见。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "m.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, exam_point, year, needs_review)
           VALUES (1, '单选', '题干一', ?, ?, '解析一', '[]', 'PDF导入', '考点A', '2024', 0)""",
        (json.dumps([{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}]), json.dumps(["A"])),
    )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_mistake_book_empty_initially(client):
    assert client.get("/mistakes").json() == []


def test_wrong_attempt_enters_mistake_book(client):
    client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})
    items = client.get("/mistakes").json()
    assert len(items) == 1
    m = items[0]
    assert m["question_id"] == 1
    assert m["stem"] == "题干一"
    assert m["wrong_answer"] == ["B"]
    assert m["correct_answer"] == ["A"]
    assert m["wrong_count"] == 1
    assert m["correct_count"] == 0
    assert m["mastery"] == "未掌握"
    assert m["first_wrong_at"] and m["last_attempt_at"]


def test_correct_attempt_does_not_enter_book(client):
    client.post("/attempts", json={"question_id": 1, "user_answer": ["A"]})
    assert client.get("/mistakes").json() == []


def test_repeat_wrong_increments_not_duplicates(client):
    client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})
    client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})
    items = client.get("/mistakes").json()
    assert len(items) == 1               # 不重复新增
    assert items[0]["wrong_count"] == 2  # 累加


def test_correct_after_wrong_tallies_correct_count(client):
    client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})  # 错
    client.post("/attempts", json={"question_id": 1, "user_answer": ["A"]})  # 对
    items = client.get("/mistakes").json()
    assert len(items) == 1
    assert items[0]["wrong_count"] == 1
    assert items[0]["correct_count"] == 1
