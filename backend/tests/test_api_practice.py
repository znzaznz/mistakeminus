"""S2 接口级测试：取题 / 作答契约。用临时库注入，不碰真实题库。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app, get_db


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "api.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    # 播种两道题：一道单选（含解析）、一道多选（needs_review，应不出现在练习里）
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, exam_point, year, needs_review)
           VALUES (1, '单选', '题干一', ?, ?, '解析一', '[]', 'PDF导入', '考点A', '2024', 0)""",
        (
            json.dumps([{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}]),
            json.dumps(["A"]),
        ),
    )
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review)
           VALUES (2, '多选', '题干二', ?, ?, '', '[]', 'PDF导入', 1)""",
        (json.dumps([{"key": "A", "text": "x"}]), json.dumps(["A"])),
    )
    # 单选但没选项（解析片段误判），应被练习接口过滤
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review)
           VALUES (3, '单选', '【答案】B【解析】…', '[]', ?, '', '[]', 'PDF导入', 0)""",
        (json.dumps(["B"]),),
    )
    # 判断题没选项是正常的（前端合成对/错），应保留
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review)
           VALUES (4, '判断', '题干四', '[]', ?, '', '[]', 'PDF导入', 0)""",
        (json.dumps(["对"]),),
    )
    # 解析片段：带了选项但题干是【答案】【解析】，应被过滤
    conn.execute(
        """INSERT INTO questions
           (id, question_type, stem, options, correct_answer, explanation,
            images, source, needs_review)
           VALUES (5, '单选', '3.【答案】B【解析】……', ?, ?, '', '[]', 'PDF导入', 0)""",
        (json.dumps([{"key": "A", "text": "x"}]), json.dumps(["B"])),
    )
    conn.commit()

    app.dependency_overrides[get_db] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()
    conn.close()


def test_list_questions_shape_and_no_answer_leak(client):
    resp = client.get("/questions?limit=10")
    assert resp.status_code == 200
    items = resp.json()
    ids = {q["id"] for q in items}
    # 排除：needs_review 的题(2)、单选无选项的解析片段(3)；保留：单选(1)、判断无选项(4)
    assert ids == {1, 4}
    q = next(q for q in items if q["id"] == 1)
    assert q["stem"] == "题干一"
    assert q["question_type"] == "单选"
    assert [o["key"] for o in q["options"]] == ["A", "B"]
    # 绝不泄露答案/解析
    assert "correct_answer" not in q
    assert "explanation" not in q


def test_submit_correct_attempt(client):
    resp = client.post("/attempts", json={"question_id": 1, "user_answer": ["A"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_correct"] is True
    assert body["correct_answer"] == ["A"]
    assert body["explanation"] == "解析一"


def test_submit_wrong_attempt(client):
    resp = client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})
    body = resp.json()
    assert body["is_correct"] is False
    assert body["correct_answer"] == ["A"]


def test_attempt_is_recorded(client):
    client.post("/attempts", json={"question_id": 1, "user_answer": ["B"]})
    client.post("/attempts", json={"question_id": 1, "user_answer": ["A"]})
    # 通过 override 拿到同一连接
    conn = app.dependency_overrides[get_db]()
    rows = conn.execute(
        "SELECT question_id, user_answer, is_correct FROM attempts ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["is_correct"] == 0
    assert rows[1]["is_correct"] == 1
    assert json.loads(rows[0]["user_answer"]) == ["B"]


def test_submit_unknown_question_404(client):
    resp = client.post("/attempts", json={"question_id": 999, "user_answer": ["A"]})
    assert resp.status_code == 404
