"""相似题 draft 规范化测试。"""

from app.extraction.schema import QuestionDraft, Option
from app.similar import normalize_similar_draft


def test_normalize_forces_question_type():
    draft = QuestionDraft(
        stem="题",
        question_type="单选",
        options=[Option(key="A", text="甲")],
        correct_answer=["A"],
    )
    out = normalize_similar_draft(draft, question_type="多选")
    assert out.question_type == "多选"


def test_normalize_judge_options():
    draft = QuestionDraft(
        stem="题",
        question_type="判断",
        options=[],
        correct_answer=["对"],
    )
    out = normalize_similar_draft(draft, question_type="判断")
    assert len(out.options) == 2
    assert out.options[0].key == "对"
