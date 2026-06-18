"""S6 归类接口测试。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db
from scripts.load_syllabus import DEFAULT_SEED, load_syllabus


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "c.db"
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
           VALUES (1, '单选', '代理题', ?, ?, '', '[]', 'PDF导入', 1, NULL),
                  (2, '单选', '可练题', ?, ?, '', '[]', 'PDF导入', 0, ?)""",
        (
            json.dumps([{"key": "A", "text": "甲"}]),
            json.dumps(["A"]),
            json.dumps([{"key": "A", "text": "甲"}]),
            json.dumps(["A"]),
            kp_id,
        ),
    )
    conn.commit()
    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app), conn, kp_id
    app.dependency_overrides.clear()
    conn.close()


def test_review_queue(client):
    c, _, _ = client
    items = c.get("/questions/review").json()
    assert len(items) == 1
    assert items[0]["id"] == 1


def test_patch_knowledge_point_clears_review(client):
    c, conn, kp_id = client
    r = c.patch(
        "/questions/1",
        json={"knowledge_point_id": kp_id, "clear_review": True},
    )
    assert r.status_code == 200
    row = conn.execute("SELECT needs_review, knowledge_point_id FROM questions WHERE id=1").fetchone()
    assert row["needs_review"] == 0
    assert row["knowledge_point_id"] == kp_id


def test_filter_by_knowledge_point(client):
    c, _, kp_id = client
    items = c.get(f"/questions?knowledge_point_id={kp_id}&limit=10").json()
    assert len(items) == 1
    assert items[0]["knowledge_point_name"] == "代理制度"
