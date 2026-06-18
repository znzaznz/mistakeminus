"""S5 数据补全纯函数测试。"""

from app.backfill import QRow, parse_number, pair_rows, plan_backfill


def test_parse_number():
    assert parse_number("5.【单选·2023】题干") == 5
    assert parse_number("17.【答案】B") == 17
    assert parse_number("无编号") is None


def test_pair_by_unique_number_with_gap():
    # 同节内按题号匹配；解析缺号2 → 真题2 配不到
    zt = [QRow(1, 1, ["A"], None), QRow(2, 2, ["B"], None), QRow(3, 3, ["C"], None)]
    jx = [QRow(101, 1, ["A"], "解析1"), QRow(103, 3, ["C"], "解析3")]
    pairs = pair_rows(zt, jx)
    assert pairs[0][1].id == 101   # 真题1 ↔ 解析号1
    assert pairs[1][1] is None     # 真题2 无号2解析
    assert pairs[2][1].id == 103   # 真题3 ↔ 解析号3


def test_pair_by_position_when_numbers_duplicate():
    # 题号重复 → 按位置配对
    zt = [QRow(1, 1, ["A"], None), QRow(2, 1, ["B"], None)]
    jx = [QRow(101, 1, ["A"], "x"), QRow(102, 1, ["B"], "y")]
    pairs = pair_rows(zt, jx)
    assert pairs[0][1].id == 101 and pairs[1][1].id == 102


def test_section_aware_pairing_handles_number_reset():
    # 两套编号：奇兵1-2 + 章后1-2，应按小节内题号匹配，不跨节错配
    zt = [QRow(1, 1, ["A"], None), QRow(2, 2, ["B"], None),
          QRow(3, 1, ["C"], None), QRow(4, 2, ["D"], None)]
    jx = [QRow(91, 1, ["A"], "奇1"), QRow(92, 2, ["B"], "奇2"),
          QRow(93, 1, ["C"], "章1"), QRow(94, 2, ["D"], "章2")]
    pairs = pair_rows(zt, jx)
    assert pairs[0][1].id == 91 and pairs[1][1].id == 92  # 奇兵节
    assert pairs[2][1].id == 93 and pairs[3][1].id == 94  # 章后节
    # 关键：真题3(章后题1) 不会错配到 奇兵解析91
    assert pairs[2][1].explanation == "章1"


def test_answer_match_backfills_explanation_only():
    zt = [QRow(1, 1, ["A"], None)]
    jx = [QRow(9, 1, ["A"], "因为甲")]
    (a,) = plan_backfill(zt, jx)
    assert a.set_answer is None            # 答案一致，不改
    assert a.set_explanation == "因为甲"
    assert a.needs_review is False


def test_missing_answer_taken_from_jiexi_confident():
    zt = [QRow(1, 1, [], None)]            # 真题缺答案
    jx = [QRow(9, 1, ["C"], "解析")]
    (a,) = plan_backfill(zt, jx)
    assert a.set_answer == ["C"]           # 解析答案权威，直接补
    assert a.set_explanation == "解析"
    assert a.needs_review is False


def test_answer_conflict_flagged_not_overwritten():
    zt = [QRow(1, 1, ["A"], None)]
    jx = [QRow(9, 1, ["B"], "解析")]
    (a,) = plan_backfill(zt, jx)
    assert a.set_answer is None            # 冲突不覆盖原答案
    assert a.needs_review is True
    assert "不一致" in a.note


def test_unmatched_zhenti_flagged():
    zt = [QRow(1, 1, ["A"], None), QRow(2, 2, ["B"], None)]
    jx = [QRow(9, 1, ["A"], "x")]          # 只有一条解析
    actions = plan_backfill(zt, jx)
    # 题号唯一：真题2 找不到号2的解析
    flagged = [a for a in actions if a.jiexi_id is None]
    assert len(flagged) == 1 and flagged[0].zhenti_id == 2
    assert flagged[0].needs_review is True
