"""load_essence 脚本单测。"""

from __future__ import annotations

import json

import pytest

from app import db
from scripts.load_essence import _parse_md, load_essence
from scripts.load_syllabus import load_syllabus

SAMPLE_MD = """\
## 1. 法律行为制度 `掌握`

- 有效要件三条

## 2. 代理制度 `掌握`

代理定义。
"""

SEED = {
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
        }
    ]
}


@pytest.fixture
def conn(tmp_path):
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    md_file = tmp_path / "knowledge-content-jingjifa-ch1.md"
    md_file.write_text(SAMPLE_MD, encoding="utf-8")
    db_file = tmp_path / "t.db"
    db.init_db(db_file)
    c = db.get_connection(db_file)
    load_syllabus(seed_file, c)
    yield c, tmp_path
    c.close()


def test_parse_md_headings():
    items = _parse_md(SAMPLE_MD)
    assert len(items) == 2
    assert items[0][0] == "法律行为制度"
    assert "有效要件" in items[0][1]


def test_load_essence_updates_empty(conn):
    c, data_dir = conn
    s = load_essence(c, force=True, data_dir=data_dir)
    assert s["updated"] == 2
    assert s["missing"] == 0
    row = c.execute(
        "SELECT essence FROM knowledge_points WHERE name = '法律行为制度'"
    ).fetchone()
    assert row["essence"] and "有效要件" in row["essence"]
