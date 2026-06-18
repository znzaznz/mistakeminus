"""S4 知识点体系建库测试：种子载入幂等 + 保留要义 + 树查询。"""

from __future__ import annotations

import json

import pytest

from app import db, repository
from scripts.load_syllabus import load_syllabus

SEED = {
    "subject": "中级会计·经济法",
    "year": 2026,
    "chapters": [
        {
            "name": "总论",
            "sections": [
                {
                    "name": "法律行为与代理",
                    "knowledge_points": [
                        {"name": "法律行为制度", "mastery": "掌握"},
                        {"name": "代理制度", "mastery": "掌握"},
                    ],
                }
            ],
        },
        {
            "name": "公司法律制度",
            "sections": [
                {
                    "name": "有限责任公司",
                    "knowledge_points": [
                        {"name": "有限责任公司设立的规定", "mastery": "掌握"}
                    ],
                }
            ],
        },
    ],
}


@pytest.fixture
def conn(tmp_path):
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    db_file = tmp_path / "s.db"
    db.init_db(db_file)
    c = db.get_connection(db_file)
    yield c, seed_file
    c.close()


def test_load_creates_taxonomy(conn):
    c, seed = conn
    summary = load_syllabus(seed, c)
    assert summary == {"exam_points": 2, "knowledge_points": 3}
    assert c.execute("SELECT COUNT(*) c FROM exam_points").fetchone()["c"] == 2
    assert c.execute("SELECT COUNT(*) c FROM knowledge_points").fetchone()["c"] == 3


def test_load_is_idempotent(conn):
    c, seed = conn
    load_syllabus(seed, c)
    load_syllabus(seed, c)  # 第二次
    assert c.execute("SELECT COUNT(*) c FROM exam_points").fetchone()["c"] == 2
    assert c.execute("SELECT COUNT(*) c FROM knowledge_points").fetchone()["c"] == 3


def test_reload_preserves_essence(conn):
    c, seed = conn
    load_syllabus(seed, c)
    # 模拟用户为某知识点补了要义
    c.execute(
        "UPDATE knowledge_points SET essence = '人工锁定的要义' WHERE name = '代理制度'"
    )
    c.commit()
    load_syllabus(seed, c)  # 再次载入不应抹掉要义
    row = c.execute(
        "SELECT essence FROM knowledge_points WHERE name = '代理制度'"
    ).fetchone()
    assert row["essence"] == "人工锁定的要义"


def test_get_taxonomy_shape(conn):
    c, seed = conn
    load_syllabus(seed, c)
    tree = repository.get_taxonomy(c)
    assert [c["chapter"] for c in tree] == ["总论", "公司法律制度"]
    ep = tree[0]["exam_points"][0]
    assert ep["name"] == "法律行为与代理"
    kp = ep["knowledge_points"][0]
    assert kp["name"] == "法律行为制度"
    assert kp["mastery_requirement"] == "掌握"
    assert kp["question_count"] == 0  # 尚未归类（S6）
    assert kp["has_essence"] is False
