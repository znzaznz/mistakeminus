"""S11 错题收藏接口测试。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "f.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review)
           VALUES (1, '单选', '题干', ?, ?, '', '[]', 'PDF导入', 0)""",
        (json.dumps([{"key": "A", "text": "甲"}]), json.dumps(["A"])),
    )
    conn.execute(
        """INSERT INTO mistakes
           (question_id, wrong_answer, correct_answer, wrong_count, correct_count,
            first_wrong_at, last_attempt_at, mastery, favorite)
           VALUES (1, '["B"]', '["A"]', 1, 0, '2026-01-01', '2026-01-01', '未掌握', 0)"""
    )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_toggle_favorite(client):
    r = client.post("/mistakes/1/favorite")
    assert r.status_code == 200
    assert r.json()["favorite"] is True
    items = client.get("/mistakes?favorite_only=true").json()
    assert len(items) == 1
    assert items[0]["favorite"] is True


def test_toggle_off(client):
    client.post("/mistakes/1/favorite")
    r = client.post("/mistakes/1/favorite")
    assert r.json()["favorite"] is False
    assert client.get("/mistakes?favorite_only=true").json() == []


def test_favorite_not_found(client):
    assert client.post("/mistakes/99/favorite").status_code == 404
