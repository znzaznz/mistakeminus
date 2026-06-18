"""S7 薄弱点分析纯函数测试。"""

from datetime import datetime

from app.weakness import KpStats, rank_weaknesses, weakness_priority


def test_rank_empty():
    assert rank_weaknesses([]) == []


def test_rank_excludes_untouched():
    stats = [
        KpStats(1, "A", "总论", "掌握", 0, 0, 0, 0, None),
        KpStats(2, "B", "总论", "掌握", 3, 3, 0, 0, "2026-06-01T10:00:00"),
    ]
    items = rank_weaknesses(stats, now=datetime(2026, 6, 18))
    assert len(items) == 1
    assert items[0].name == "B"
    assert items[0].accuracy == 1.0


def test_rank_all_wrong_high_priority():
    now = datetime(2026, 6, 18)
    weak = KpStats(1, "弱", "总论", "掌握", 5, 1, 4, 3, "2026-06-01T10:00:00")
    strong = KpStats(2, "强", "总论", "了解", 5, 5, 0, 0, "2026-06-17T10:00:00")
    items = rank_weaknesses([weak, strong], now=now)
    assert items[0].name == "弱"
    assert items[0].priority > items[1].priority
    assert "正确率低" in items[0].tags


def test_stale_gets_tag():
    stats = KpStats(1, "久", "总论", "熟悉", 2, 2, 0, 1, "2026-05-01T10:00:00")
    items = rank_weaknesses([stats], now=datetime(2026, 6, 18))
    assert "久未复习" in items[0].tags


def test_priority_negative_for_no_activity():
    s = KpStats(1, "X", "总论", "掌握", 0, 0, 0, 0, None)
    assert weakness_priority(s, datetime(2026, 6, 18)) < 0
