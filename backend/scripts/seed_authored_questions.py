"""把人工编写的题目（贴知识点要义）批量入库，带结构质量闸门。

用法：python -m scripts.seed_authored_questions <questions.json> [--review]

JSON 为题目列表，每题字段：
  knowledge_point_id, question_type(单选/多选/判断), stem,
  options(单选/多选必填: [{"key":"A","text":"..."}]),
  correct_answer(["A"]/["A","C"]/["对"]/["错"]), explanation

质量闸门（不通过直接拒绝整批，不写库）：
  - knowledge_point_id 必须存在
  - 单选恰好 1 个答案、多选 ≥2 个、判断答案 ∈ {对,错}
  - 单选/多选选项 key 唯一、答案必须是已有选项 key
  - stem 不得夹带 【答案】/【解析】（防解析污染串进题干）
  - 同一知识点内题干去重
来源固定 source='Claude自编'。默认 needs_review=0（可刷）；--review 则入待复核队列。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app import db

SOURCE = "Claude自编"
VALID_TYPES = {"单选", "多选", "判断"}


def validate(items: list[dict], valid_kp: set[int]) -> list[str]:
    errors: list[str] = []
    for i, q in enumerate(items):
        tag = f"#{i} kp={q.get('knowledge_point_id')}"
        kp = q.get("knowledge_point_id")
        if kp not in valid_kp:
            errors.append(f"{tag}: knowledge_point_id 不存在")
        qt = q.get("question_type")
        if qt not in VALID_TYPES:
            errors.append(f"{tag}: question_type 非法 {qt!r}")
            continue
        stem = (q.get("stem") or "").strip()
        if not stem:
            errors.append(f"{tag}: 空题干")
        if "【答案】" in stem or "【解析】" in stem:
            errors.append(f"{tag}: 题干夹带答案/解析")
        ans = q.get("correct_answer") or []
        if qt == "判断":
            if ans not in (["对"], ["错"]):
                errors.append(f"{tag}: 判断答案须为 ['对'] 或 ['错']，实际 {ans}")
        else:
            opts = q.get("options") or []
            keys = [o.get("key") for o in opts]
            if len(opts) < 2:
                errors.append(f"{tag}: 选项不足 2 个")
            if len(keys) != len(set(keys)):
                errors.append(f"{tag}: 选项 key 重复 {keys}")
            if any(not (o.get("text") or "").strip() for o in opts):
                errors.append(f"{tag}: 存在空选项文本")
            if qt == "单选" and len(ans) != 1:
                errors.append(f"{tag}: 单选答案须恰好 1 个，实际 {ans}")
            if qt == "多选" and len(ans) < 2:
                errors.append(f"{tag}: 多选答案须 ≥2 个，实际 {ans}")
            if any(a not in keys for a in ans):
                errors.append(f"{tag}: 答案 {ans} 不在选项 {keys} 中")
        if not (q.get("explanation") or "").strip():
            errors.append(f"{tag}: 缺解析")
    # 同知识点题干去重
    seen: dict[tuple, int] = {}
    for i, q in enumerate(items):
        sig = (q.get("knowledge_point_id"), (q.get("stem") or "").strip())
        if sig in seen:
            errors.append(f"#{i}: 与 #{seen[sig]} 题干在同一知识点内重复")
        else:
            seen[sig] = i
    return errors


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    needs_review = 1 if "--review" in sys.argv else 0
    if not args:
        print(__doc__)
        return 2
    items = json.loads(Path(args[0]).read_text(encoding="utf-8"))

    db.init_db()
    conn = db.get_connection()
    try:
        valid_kp = {r["id"] for r in conn.execute("SELECT id FROM knowledge_points")}
        kp_meta = {
            r["id"]: (r["chapter"], r["exam_point"])
            for r in conn.execute(
                "SELECT kp.id, ep.chapter, ep.name AS exam_point "
                "FROM knowledge_points kp JOIN exam_points ep ON kp.exam_point_id=ep.id"
            )
        }
        errors = validate(items, valid_kp)
        # 与库内已存在题干去重（防重复运行/与既有题撞车）
        existing = {
            (r["knowledge_point_id"], r["stem"].strip())
            for r in conn.execute(
                "SELECT knowledge_point_id, stem FROM questions WHERE knowledge_point_id IS NOT NULL"
            )
        }
        items = [
            q for q in items
            if (q.get("knowledge_point_id"), (q.get("stem") or "").strip()) not in existing
        ]
        if errors:
            print(f"质量闸门未通过，{len(errors)} 处问题，未写库：")
            for e in errors:
                print("  -", e)
            return 1

        inserted = 0
        for q in items:
            kp = q["knowledge_point_id"]
            chapter, exam_point = kp_meta.get(kp, (None, None))
            conn.execute(
                """INSERT INTO questions
                   (chapter, exam_point, question_type, stem, options, correct_answer,
                    explanation, source, needs_review, knowledge_point_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    chapter, exam_point, q["question_type"], q["stem"].strip(),
                    json.dumps(q.get("options", []), ensure_ascii=False),
                    json.dumps(q["correct_answer"], ensure_ascii=False),
                    (q.get("explanation") or "").strip(),
                    SOURCE, needs_review, kp,
                ),
            )
            inserted += 1
        conn.commit()
        print(f"入库 {inserted} 题（source={SOURCE}, needs_review={needs_review}）；"
              f"跳过已存在 {len(json.loads(Path(args[0]).read_text(encoding='utf-8'))) - inserted - 0} 重复")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
