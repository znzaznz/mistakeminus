"""S3 错题本状态机纯函数测试。"""

from app.mistakes import MistakeRecord, apply_attempt


def test_correct_and_not_in_book_stays_out():
    rec = apply_attempt(
        None, is_correct=True, user_answer=["A"], correct_answer=["A"], now="t0"
    )
    assert rec is None  # 答对的新题不进错题本


def test_first_wrong_creates_record():
    rec = apply_attempt(
        None, is_correct=False, user_answer=["B"], correct_answer=["A"], now="t0"
    )
    assert rec is not None
    assert rec.wrong_count == 1
    assert rec.correct_count == 0
    assert rec.wrong_answer == ["B"]
    assert rec.correct_answer == ["A"]
    assert rec.first_wrong_at == "t0"
    assert rec.last_attempt_at == "t0"
    assert rec.mastery == "未掌握"


def test_repeat_wrong_increments_and_keeps_first_time():
    first = apply_attempt(
        None, is_correct=False, user_answer=["B"], correct_answer=["A"], now="t0"
    )
    second = apply_attempt(
        first, is_correct=False, user_answer=["C"], correct_answer=["A"], now="t1"
    )
    assert second.wrong_count == 2
    assert second.wrong_answer == ["C"]       # 更新为最近错误答案
    assert second.first_wrong_at == "t0"       # 首次做错时间不变
    assert second.last_attempt_at == "t1"      # 最近时间更新


def test_correct_on_existing_increments_correct_count():
    first = apply_attempt(
        None, is_correct=False, user_answer=["B"], correct_answer=["A"], now="t0"
    )
    after = apply_attempt(
        first, is_correct=True, user_answer=["A"], correct_answer=["A"], now="t2"
    )
    assert after.wrong_count == 1
    assert after.correct_count == 1
    assert after.last_attempt_at == "t2"
    assert after.first_wrong_at == "t0"


def test_record_is_immutable_input_unchanged():
    first = MistakeRecord(
        wrong_answer=["B"], correct_answer=["A"], wrong_count=1, correct_count=0,
        first_wrong_at="t0", last_attempt_at="t0",
    )
    apply_attempt(first, is_correct=False, user_answer=["C"], correct_answer=["A"], now="t1")
    assert first.wrong_count == 1  # 原记录未被修改
