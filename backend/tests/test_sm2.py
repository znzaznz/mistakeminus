"""S9 SM-2 与每日任务纯函数测试。"""

from datetime import date

from app.daily_task import generate_task_question_ids, mastery_weight
from app.sm2 import Sm2State, is_due, quality_from_correct, sm2_schedule


def test_quality_mapping():
    assert quality_from_correct(True) == 4
    assert quality_from_correct(False) == 0


def test_sm2_first_correct():
    s = sm2_schedule(Sm2State(), 4, date(2026, 6, 1))
    assert s.repetition == 1
    assert s.interval_days == 1
    assert s.due_date == "2026-06-02"


def test_sm2_second_correct_longer_interval():
    s0 = Sm2State(repetition=1, interval_days=1, due_date="2026-06-02")
    s = sm2_schedule(s0, 4, date(2026, 6, 2))
    assert s.repetition == 2
    assert s.interval_days == 6


def test_sm2_wrong_resets():
    s0 = Sm2State(repetition=3, interval_days=15, ease=2.5)
    s = sm2_schedule(s0, 0, date(2026, 6, 1))
    assert s.repetition == 0
    assert s.interval_days == 1


def test_generate_task_due_first():
    ids = generate_task_question_ids(
        due_ids=[1, 2],
        new_candidates=[(3, 3.0), (4, 1.0)],
        target=3,
    )
    assert ids == [1, 2, 3]


def test_generate_task_dedupe():
    ids = generate_task_question_ids(
        due_ids=[1],
        new_candidates=[(1, 2.0), (2, 1.0)],
        target=5,
    )
    assert 1 in ids and ids.count(1) == 1


def test_is_due():
    assert is_due("2026-06-01", date(2026, 6, 18))
    assert not is_due("2026-12-01", date(2026, 6, 18))


def test_mastery_weight():
    assert mastery_weight("掌握") > mastery_weight("了解")
