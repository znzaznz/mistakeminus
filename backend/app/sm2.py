"""S9 SM-2 调度纯函数。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MIN_EASE = 1.3
DEFAULT_EASE = 2.5


@dataclass(frozen=True)
class Sm2State:
    ease: float = DEFAULT_EASE
    interval_days: int = 0
    repetition: int = 0
    due_date: str | None = None  # YYYY-MM-DD


def quality_from_correct(is_correct: bool) -> int:
    """对错 → SM-2 质量分：答对=良好(4)，答错=重来(0)。"""
    return 4 if is_correct else 0


def sm2_schedule(
    state: Sm2State,
    quality: int,
    today: date,
) -> Sm2State:
    """SM-2 一步调度，返回新状态。"""
    ease = state.ease
    interval = state.interval_days
    repetition = state.repetition

    if quality < 3:
        repetition = 0
        interval = 1
    else:
        if repetition == 0:
            interval = 1
        elif repetition == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        repetition += 1

    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease < MIN_EASE:
        ease = MIN_EASE

    due = today + timedelta(days=interval)
    return Sm2State(
        ease=round(ease, 2),
        interval_days=interval,
        repetition=repetition,
        due_date=due.isoformat(),
    )


def is_due(due_date: str | None, today: date) -> bool:
    if not due_date:
        return False
    return date.fromisoformat(due_date) <= today
