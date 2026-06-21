"""Generate AI booster questions so each knowledge point has a minimum count.

Generated questions are source-isolated and marked ``needs_review=1``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from app import db
from app.config import settings
from app.extraction.schema import validate_draft


ROOT = Path.home() / "Downloads" / "needreadfile_output"
REPORT = ROOT / "_ai_kp_booster_report.json"
SOURCE = "AI知识点补强"

PROMPT = """你是中级会计职称《经济法》命题老师。
请围绕指定知识点生成 {count} 道可刷题，题型混合使用单选、多选、判断。

硬性要求：
1. 只考这个知识点，不要串到同章其他知识点。
2. 题干必须是中文，贴近中级会计经济法机考风格。
3. 单选/多选必须有 A-D 四个选项；判断题 options 用“对/错”两个选项。
4. 多选题 correct_answer 至少 2 个；单选/判断只有 1 个。
5. 每题必须有简明解析，说明为什么选这个答案。
6. 不要引用“根据上述资料”等缺失上下文的话。
7. 不要照抄已有真题，换场景、换问法。
8. 只输出最终题目，不要在解析里出现“更正、修正、重新核定、最终确认、原解析有误”等自我纠错过程。

章节：{chapter}
考点：{exam_point}
知识点：{knowledge_point}

知识点要义：
{essence}

输出严格 JSON 数组，不要 markdown，不要解释。数组元素格式：
{{
  "stem": "...",
  "question_type": "单选/多选/判断",
  "options": [{{"key":"A","text":"..."}}, {{"key":"B","text":"..."}}, {{"key":"C","text":"..."}}, {{"key":"D","text":"..."}}],
  "correct_answer": ["A"],
  "explanation": "..."
}}
"""


def _backup_db() -> Path:
    src = settings.db_path
    dst = src.with_suffix(f".db.bak-ai-kp-booster-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(src, dst)
    return dst


def _client() -> OpenAI:
    if not settings.dashscope_api_key.strip():
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)


def _json_from_text(text: str) -> Any:
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = s.find("[")
        if start < 0:
            raise
        return json.JSONDecoder().raw_decode(s[start:])[0]


def _question_counts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT
                kp.id AS knowledge_point_id,
                ep.chapter,
                ep.name AS exam_point,
                kp.name AS knowledge_point,
                kp.essence,
                COUNT(q.id) AS current_count
            FROM knowledge_points kp
            JOIN exam_points ep ON ep.id = kp.exam_point_id
            LEFT JOIN questions q ON q.knowledge_point_id = kp.id
            GROUP BY kp.id
            ORDER BY ep.seq, kp.seq
            """
        )
    ]


def _generate(client: OpenAI, row: dict[str, Any], count: int) -> list[dict[str, Any]]:
    prompt = PROMPT.format(
        count=count,
        chapter=row["chapter"],
        exam_point=row["exam_point"],
        knowledge_point=row["knowledge_point"],
        essence=row.get("essence") or "本知识点暂无要义，请按知识点名称和中级经济法常规范围命题。",
    )
    resp = client.chat.completions.create(
        model=settings.qwen_text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    data = _json_from_text(resp.choices[0].message.content or "")
    if not isinstance(data, list):
        raise ValueError("model did not return a JSON array")
    return [x for x in data if isinstance(x, dict)]


def _quality_gate(raw: dict[str, Any]) -> str | None:
    text = json.dumps(raw, ensure_ascii=False)
    banned = ["更正", "修正", "重新核定", "最终确认", "原解析有误", "重设", "回归法理"]
    for word in banned:
        if word in text:
            return f"contains self-correction text: {word}"
    return None


def _insert(conn: sqlite3.Connection, row: dict[str, Any], raw: dict[str, Any]) -> int:
    quality_error = _quality_gate(raw)
    if quality_error:
        raise ValueError(quality_error)
    draft, err = validate_draft(raw)
    if draft is None:
        raise ValueError(err)
    cur = conn.execute(
        """
        INSERT INTO questions
            (chapter, exam_point, question_type, difficulty, year, stem,
             options, correct_answer, explanation, images, source, source_ref,
             confidence, needs_review, knowledge_point_id)
        VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, '[]', ?, ?, 0.75, 1, ?)
        """,
        (
            row["chapter"],
            row["exam_point"],
            draft.question_type,
            draft.stem,
            json.dumps([o.model_dump() for o in draft.options], ensure_ascii=False),
            json.dumps(draft.correct_answer, ensure_ascii=False),
            draft.explanation or "",
            SOURCE,
            f"kp_booster:{row['knowledge_point_id']}:{datetime.now():%Y%m%d}",
            row["knowledge_point_id"],
        ),
    )
    return int(cur.lastrowid)


def run(*, target: int, limit_kp: int | None, dry: bool) -> dict[str, Any]:
    db.init_db()
    conn = db.get_connection()
    client = _client()
    backup = None if dry else str(_backup_db())
    report: dict[str, Any] = {
        "target_per_knowledge_point": target,
        "dry": dry,
        "backup": backup,
        "items": [],
        "inserted": 0,
        "errors": [],
    }
    try:
        todo = []
        for row in _question_counts(conn):
            need = max(0, target - int(row["current_count"]))
            if need:
                row["need"] = need
                todo.append(row)
        if limit_kp is not None:
            todo = todo[:limit_kp]

        for row in todo:
            try:
                raws = _generate(client, row, int(row["need"]))
                inserted_ids: list[int | None] = []
                for raw in raws[: int(row["need"])]:
                    inserted_ids.append(None if dry else _insert(conn, row, raw))
                if not dry:
                    conn.commit()
                report["inserted"] += len(inserted_ids)
                report["items"].append(
                    {
                        "knowledge_point_id": row["knowledge_point_id"],
                        "chapter": row["chapter"],
                        "exam_point": row["exam_point"],
                        "knowledge_point": row["knowledge_point"],
                        "needed": row["need"],
                        "generated": len(raws),
                        "inserted_ids": inserted_ids,
                    }
                )
                print(f"kp {row['knowledge_point_id']} generated {len(inserted_ids)}/{row['need']}")
            except Exception as e:
                report["errors"].append(
                    {
                        "knowledge_point_id": row["knowledge_point_id"],
                        "knowledge_point": row["knowledge_point"],
                        "error": str(e),
                    }
                )
                print(f"kp {row['knowledge_point_id']} failed: {e}")
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=6)
    parser.add_argument("--limit-kp", type=int)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    result = run(target=args.target, limit_kp=args.limit_kp, dry=args.dry)
    print(json.dumps({k: result[k] for k in ["target_per_knowledge_point", "dry", "backup", "inserted", "errors"]}, ensure_ascii=False, indent=2))
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
