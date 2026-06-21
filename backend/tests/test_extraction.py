"""S1 提取管线测试。VLM 调用全程 mock，不依赖真实 API key。"""

from __future__ import annotations

import glob
import json

import fitz
import pytest

from app import db
from app.config import PROJECT_ROOT
from app.extraction import pdf
from app.extraction.importer import import_pdf
from app.extraction.schema import validate_draft
from app.extraction import vlm
from app.extraction.vlm import _parse_questions_json


# ----------------------------- schema 校验 -----------------------------

def test_valid_draft_passes():
    draft, err = validate_draft(
        {
            "stem": "下列属于民事法律行为的是？",
            "question_type": "单选",
            "options": [{"key": "A", "text": "甲乙签合同"}],
            "correct_answer": "A",
            "confidence": 0.9,
        }
    )
    assert err is None
    assert draft is not None
    assert draft.correct_answer == ["A"]


def test_multi_answer_string_is_split():
    draft, _ = validate_draft(
        {"stem": "x", "question_type": "多选", "correct_answer": "AC"}
    )
    assert draft.correct_answer == ["A", "C"]


def test_judge_answer_preserved():
    draft, _ = validate_draft(
        {"stem": "x", "question_type": "判断", "correct_answer": "对"}
    )
    assert draft.correct_answer == ["对"]


def test_year_int_is_coerced_to_str():
    # VLM 常把年份返回成整数，不应因此判废
    draft, err = validate_draft(
        {"stem": "x", "question_type": "单选", "year": 2024}
    )
    assert err is None
    assert draft.year == "2024"


def test_invalid_question_type_rejected():
    draft, err = validate_draft({"stem": "x", "question_type": "填空"})
    assert draft is None
    assert err is not None


def test_empty_stem_rejected():
    draft, err = validate_draft({"stem": "", "question_type": "单选"})
    assert draft is None
    assert err is not None


# --------------------------- VLM 返回解析 ---------------------------

def test_parse_plain_json():
    qs = _parse_questions_json('{"questions": [{"stem": "x"}]}')
    assert qs == [{"stem": "x"}]


def test_parse_fenced_json():
    qs = _parse_questions_json('```json\n{"questions": [{"stem": "y"}]}\n```')
    assert qs == [{"stem": "y"}]


def test_parse_json_with_trailing_extra_data():
    # 模型在 JSON 后多输出了说明文字，不应整页丢弃
    qs = _parse_questions_json('{"questions": [{"stem": "z"}]}\n以上是识别结果。')
    assert qs == [{"stem": "z"}]


def test_ollama_extract_posts_image(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": '{"questions": [{"stem": "x"}]}'}

    seen = {}

    class FakeClient:
        def __init__(self, trust_env, timeout):
            seen["trust_env"] = trust_env
            seen["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, json):
            seen["url"] = url
            seen["json"] = json
            return FakeResponse()

    monkeypatch.setattr(vlm.httpx, "Client", FakeClient)
    qs = vlm._extract_questions_ollama(b"png")

    assert qs == [{"stem": "x"}]
    assert seen["trust_env"] is False
    assert seen["url"].endswith("/api/generate")
    assert seen["json"]["images"] == ["cG5n"]


# --------------------- pdf.py 在真实 PDF 上的确定性 ---------------------

@pytest.fixture(scope="module")
def real_pdf_page():
    pdfs = sorted(glob.glob(str(PROJECT_ROOT / "*.pdf")))
    if not pdfs:
        pytest.skip("项目根目录没有真实 PDF，跳过")
    doc = fitz.open(pdfs[0])
    yield doc[3]  # 第4页：已知有内容配图
    doc.close()


def test_render_page_png_nonempty(real_pdf_page):
    png = pdf.render_page_png(real_pdf_page)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数
    pix = fitz.Pixmap(png)
    # 2x 缩放下 A4 约 1190x1684
    assert pix.width > 1000 and pix.height > 1400


def test_content_image_rects_found(real_pdf_page):
    rects = pdf.content_image_rects(real_pdf_page)
    assert len(rects) >= 1  # 第4页有内容配图


def test_crop_render_is_not_blank(real_pdf_page):
    rects = pdf.content_image_rects(real_pdf_page)
    png = pdf.crop_render_png(real_pdf_page, rects[0])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert not pdf.is_blank_png(png)  # 关键：不能是全黑图


# --------------------- importer 端到端（mock VLM）---------------------

def _make_synthetic_pdf(path, with_image: bool):
    """造一份含一道（可选带嵌入图）题目的 PDF。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 700), "synthetic question page")
    if with_image:
        # 在内容区放一张彩色嵌入图
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 120))
        pix.set_rect(pix.irect, (200, 60, 30))  # 非全黑的橙红
        page.insert_image(fitz.Rect(120, 300, 240, 420), pixmap=pix)
    doc.save(path)
    doc.close()


@pytest.fixture
def temp_conn(tmp_path):
    db_file = tmp_path / "test.db"
    db.init_db(db_file)
    conn = db.get_connection(db_file)
    yield conn
    conn.close()


def test_import_writes_questions(temp_conn, tmp_path):
    pdf_path = tmp_path / "syn.pdf"
    _make_synthetic_pdf(pdf_path, with_image=False)

    def fake_extract(_png):
        return [
            {
                "stem": "题干1",
                "question_type": "单选",
                "options": [{"key": "A", "text": "甲"}, {"key": "B", "text": "乙"}],
                "correct_answer": "A",
                "exam_point": "考点一",
                "confidence": 0.95,
            }
        ]

    summary = import_pdf(pdf_path, fake_extract, temp_conn, media_dir=tmp_path / "media")
    assert summary.imported == 1
    assert summary.needs_review == 0

    row = temp_conn.execute("SELECT * FROM questions").fetchone()
    assert row["stem"] == "题干1"
    assert row["source"] == "PDF导入"
    assert json.loads(row["correct_answer"]) == ["A"]
    assert row["source_ref"].endswith("#page=1")


def test_low_confidence_flags_needs_review(temp_conn, tmp_path):
    pdf_path = tmp_path / "syn.pdf"
    _make_synthetic_pdf(pdf_path, with_image=False)

    def fake_extract(_png):
        return [{"stem": "模糊题", "question_type": "单选", "confidence": 0.4}]

    summary = import_pdf(pdf_path, fake_extract, temp_conn, media_dir=tmp_path / "media")
    assert summary.imported == 1
    assert summary.needs_review == 1
    row = temp_conn.execute("SELECT needs_review FROM questions").fetchone()
    assert row["needs_review"] == 1


def test_invalid_payload_counted_not_imported(temp_conn, tmp_path):
    pdf_path = tmp_path / "syn.pdf"
    _make_synthetic_pdf(pdf_path, with_image=False)

    def fake_extract(_png):
        return [{"stem": "x", "question_type": "填空"}]  # 非法题型

    summary = import_pdf(pdf_path, fake_extract, temp_conn, media_dir=tmp_path / "media")
    assert summary.imported == 0
    assert summary.invalid == 1
    assert temp_conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"] == 0


def test_image_question_gets_cropped_image(temp_conn, tmp_path):
    pdf_path = tmp_path / "syn.pdf"
    _make_synthetic_pdf(pdf_path, with_image=True)
    media = tmp_path / "media"

    def fake_extract(_png):
        return [
            {"stem": "带图题", "question_type": "单选", "has_image": True, "confidence": 0.9}
        ]

    summary = import_pdf(pdf_path, fake_extract, temp_conn, media_dir=media)
    assert summary.imported == 1

    row = temp_conn.execute("SELECT images FROM questions").fetchone()
    images = json.loads(row["images"])
    assert len(images) == 1
    saved = media / images[0]
    assert saved.exists() and saved.stat().st_size > 0
