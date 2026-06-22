"""上传页管线单测（不调用真实 API）。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app import db
from app.upload_pipeline import format_ocr_question_text, process_screenshot_upload


def test_format_ocr_question_text():
    text = format_ocr_question_text(
        {
            "stem": "题干",
            "options": [{"key": "A", "text": "甲"}],
        }
    )
    assert "题干" in text
    assert "A. 甲" in text


MOCK_OCR = [
    {
        "stem": "【例7】（多选·2022）测试题干",
        "question_type": "多选",
        "options": [
            {"key": "A", "text": "选项A"},
            {"key": "B", "text": "选项B"},
        ],
        "correct_answer": [],
        "explanation": "",
        "chapter": "第二节 资产可收回金额",
        "answer_visible": False,
        "explanation_visible": False,
        "confidence": 0.9,
    }
]

MOCK_SUBJECT = {"subject": "中级会计实务", "confidence": 0.95}
MOCK_CLASSIFY = {"knowledge_point_name": "资产可收回金额的计量", "confidence": 0.88}
MOCK_ENRICH = {
    "correct_answer": ["B"],
    "explanation": "测试解析",
    "answer_inferred": True,
    "explanation_generated": True,
}


@pytest.fixture
def conn(tmp_path):
    db_file = tmp_path / "up.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    conn.execute(
        "INSERT INTO exam_points (id, subject, chapter, name, seq) VALUES (1, '中级会计实务', '资产减值', '考点', 1)"
    )
    conn.execute(
        """
        INSERT INTO knowledge_points (id, exam_point_id, name, essence, seq)
        VALUES (10, 1, '资产可收回金额的计量', '要义', 1)
        """
    )
    conn.commit()
    yield conn
    conn.close()


@patch("app.upload_pipeline.enrich_missing_fields", return_value=MOCK_ENRICH)
@patch("app.upload_pipeline.classify_question", return_value=MOCK_CLASSIFY)
@patch("app.upload_pipeline.infer_subject", return_value=MOCK_SUBJECT)
@patch("app.upload_pipeline.polish_ocr_question")
@patch("app.upload_pipeline.vlm.extract_screenshot", return_value=MOCK_OCR)
def test_process_screenshot_upload(mock_vlm, mock_polish, mock_subj, mock_cls, mock_enr, conn):
    mock_polish.side_effect = lambda o: {**o, "text_polished": True}
    out = process_screenshot_upload(conn, b"png")
    assert out["stem"].startswith("【例7】")
    assert out["subject"] == "中级会计实务"
    assert out["knowledge_point_id"] == 10
    assert out["correct_answer"] == ["B"]
    assert out["explanation"] == "测试解析"
    assert out["answer_inferred"] is True
    assert out["text_polished"] is True
    mock_vlm.assert_called_once()
    mock_polish.assert_called_once()


def test_polish_ocr_question_strips_invented_answer():
    from app.llm import polish_ocr_question

    ocr = {
        "stem": "题干",
        "question_type": "单选",
        "options": [{"key": "A", "text": "甲"}],
        "correct_answer": ["A"],
        "explanation": "解析",
        "answer_visible": False,
        "explanation_visible": False,
        "confidence": 0.8,
    }

    class FakeMsg:
        content = json.dumps(
            {
                "stem": "题干润色",
                "question_type": "单选",
                "options": [{"key": "A", "text": "甲"}],
                "correct_answer": ["A"],
                "explanation": "不该出现",
            },
            ensure_ascii=False,
        )

    class FakeChoice:
        message = FakeMsg()

    class FakeResp:
        choices = [FakeChoice()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return FakeResp()

    out = polish_ocr_question(ocr, client=FakeClient())
    assert out["stem"] == "题干润色"
    assert out["correct_answer"] == []
    assert out["explanation"] == ""
    assert out["text_polished"] is True
