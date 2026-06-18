"""S6 题目归类纯函数测试。"""

from app.classify import (
    CLASSIFY_CONFIDENCE_THRESHOLD,
    format_question_text,
    infer_chapter_from_source,
    keyword_classify,
    plan_classification,
    resolve_knowledge_point_id,
)


def test_format_question_text():
    text = format_question_text(
        "1. 单选题",
        '[{"key":"A","text":"甲"},{"key":"B","text":"乙"}]',
    )
    assert "题干" in text
    assert "A. 甲" in text


def test_resolve_exact_and_fuzzy():
    m = {"代理制度": 4, "法律行为制度": 3}
    assert resolve_knowledge_point_id("代理制度", m) == 4
    assert resolve_knowledge_point_id("代理制度 `掌握`", m) == 4


def test_plan_high_confidence():
    o = plan_classification(
        knowledge_point_name="代理制度",
        confidence=0.9,
        name_to_id={"代理制度": 4},
        threshold=CLASSIFY_CONFIDENCE_THRESHOLD,
    )
    assert o.knowledge_point_id == 4
    assert o.needs_review is False


def test_plan_low_confidence_still_assigns():
    o = plan_classification(
        knowledge_point_name="代理制度",
        confidence=0.5,
        name_to_id={"代理制度": 4},
    )
    assert o.knowledge_point_id == 4
    assert o.needs_review is True


def test_keyword_statute_of_limitations():
    m = {"民事诉讼法律制度的规定": 7, "法律行为制度": 3}
    o = keyword_classify("关于诉讼时效中断的表述", m)
    assert o is not None
    assert o.knowledge_point_id == 7
    assert o.needs_review is False


def test_plan_unknown_name():
    o = plan_classification(
        knowledge_point_name="不存在",
        confidence=0.9,
        name_to_id={"代理制度": 4},
    )
    assert o.knowledge_point_id is None
    assert o.needs_review is True


def test_infer_chapter_from_pdf_name():
    assert infer_chapter_from_source("周周老师-第三章 合伙企业法律制度852251.pdf#page=1") == "合伙企业法律制度"
    assert infer_chapter_from_source("周周老师-第二部分 客观题集训138003.pdf#page=2") == "公司法律制度"
    assert infer_chapter_from_source("刘琪老师-第一章 总论280619.pdf#page=3") == "总论"
