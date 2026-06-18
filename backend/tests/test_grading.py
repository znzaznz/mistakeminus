"""S2 判题纯函数测试，覆盖单选/多选/判断及边界。"""

from app.grading import judge


def test_single_choice_correct():
    assert judge(["A"], ["A"]) is True


def test_single_choice_wrong():
    assert judge(["A"], ["B"]) is False


def test_multi_choice_exact_match():
    assert judge(["A", "C"], ["C", "A"]) is True  # 顺序无关


def test_multi_choice_missing_one_is_wrong():
    assert judge(["A", "C"], ["A"]) is False  # 漏选


def test_multi_choice_extra_one_is_wrong():
    assert judge(["A", "C"], ["A", "B", "C"]) is False  # 多选


def test_judge_true_false():
    assert judge(["对"], ["对"]) is True
    assert judge(["对"], ["错"]) is False


def test_case_and_whitespace_insensitive():
    assert judge(["A"], [" a "]) is True


def test_empty_user_answer_is_wrong():
    assert judge(["A"], []) is False
