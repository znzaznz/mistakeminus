"""计划 A 集训解析器测试。"""

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from app.extraction.jixun import parse_jixun_pdf

MEDIA = PROJECT_ROOT / "media"
JIXUN_PDFS = sorted(MEDIA.glob("*客观题集训*.pdf"))


@pytest.mark.skipif(not JIXUN_PDFS, reason="无集训 PDF")
@pytest.mark.parametrize("pdf_path", JIXUN_PDFS, ids=lambda p: p.name[-12:])
def test_jixun_alignment(pdf_path: Path):
    report = parse_jixun_pdf(pdf_path)
    assert report.question_count == report.answer_count
    assert not report.missing_in_answers
    assert not report.missing_in_questions
    assert report.continuous
    assert report.chapter
    assert len(report.drafts) == report.question_count
    for d in report.drafts:
        assert d.stem
        assert d.correct_answer
        assert d.question_type in ("单选", "多选", "判断")


@pytest.mark.skipif(not JIXUN_PDFS, reason="无集训 PDF")
def test_jixun_sample_has_explanation():
    report = parse_jixun_pdf(JIXUN_PDFS[0])
    with_expl = [d for d in report.drafts if d.explanation]
    assert len(with_expl) >= report.question_count * 0.9
