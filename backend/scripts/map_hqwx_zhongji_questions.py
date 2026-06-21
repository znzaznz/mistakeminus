"""Semantically map HQWX Zhongji PDF questions to local knowledge points."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402


SOURCE = "环球网校中级真题PDF"
OUT = ROOT / "data" / "imports" / "reports" / "_hqwx_zhongji_semantic_mapping.json"
SUBJECTS = {"经济法", "中级会计实务", "财务管理"}


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(settings.db_path)
    c.row_factory = sqlite3.Row
    return c


def client() -> OpenAI:
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)


def load_kps(c: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    rows = c.execute(
        """
        SELECT kp.id, ep.subject, ep.chapter, ep.name AS exam_point, kp.name AS knowledge_point
        FROM knowledge_points kp
        JOIN exam_points ep ON ep.id = kp.exam_point_id
        ORDER BY ep.subject, ep.seq, kp.seq
        """
    ).fetchall()
    out = {s: [] for s in SUBJECTS}
    for r in rows:
        out[r["subject"]].append(dict(r))
    return out


def load_questions(c: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = c.execute(
        """
        SELECT q.id, q.chapter, q.exam_point, q.question_type, q.stem, q.options,
               q.correct_answer, q.explanation,
               COALESCE(ep.subject, CASE WHEN q.chapter IN ('经济法','中级会计实务','财务管理') THEN q.chapter END) AS subject
        FROM questions q
        LEFT JOIN knowledge_points kp ON kp.id = q.knowledge_point_id
        LEFT JOIN exam_points ep ON ep.id = kp.exam_point_id
        WHERE q.source = ?
        ORDER BY q.id
        """,
        (SOURCE,),
    ).fetchall()
    return [dict(r) for r in rows]


def json_from_text(text: str) -> Any:
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


def short_json(value: str) -> str:
    try:
        data = json.loads(value or "[]")
    except json.JSONDecodeError:
        return value or ""
    return json.dumps(data, ensure_ascii=False)


def make_prompt(subject: str, kps: list[dict[str, Any]], batch: list[dict[str, Any]]) -> str:
    kp_text = "\n".join(
        f"{kp['id']} | {kp['chapter']} | {kp['exam_point']} | {kp['knowledge_point']}"
        for kp in kps
    )
    q_lines = []
    for i, q in enumerate(batch):
        q_lines.append(
            "\n".join(
                [
                    f"index={i}, question_id={q['id']}",
                    f"题型：{q['question_type']}",
                    f"题干：{q['stem']}",
                    f"选项：{short_json(q['options'])}",
                    f"答案：{short_json(q['correct_answer'])}",
                    f"解析：{q['explanation'] or ''}",
                ]
            )
        )
    q_text = "\n\n".join(q_lines)
    return f"""你要把《{subject}》中级会计真题逐题映射到本项目的知识点。

要求：
1. 每道题必须给一个 primary_knowledge_point_id。除非题目明显不是本学科、解析严重串题、无法判断，才填 null。
2. 可以给 related_knowledge_point_ids，最多 3 个，用于记录交叉考点；主知识点必须是最核心、最直接考查的知识点。
3. 只能使用下面清单里的知识点 id，不要编造 id。
4. 不要只看题干关键词，要结合选项、答案、解析判断。解析里有“本题考核/知识点”时优先参考，但仍要确认是否和题干一致。
5. 输出严格 JSON 数组，长度必须等于题目数。不要输出 Markdown。

输出格式：
[
  {{
    "index": 0,
    "question_id": 123,
    "primary_knowledge_point_id": 456,
    "related_knowledge_point_ids": [457],
    "confidence": 0.86,
    "reason": "简短说明为什么对应这个知识点"
  }}
]

知识点清单：
{kp_text}

题目：
{q_text}
"""


def map_batch(
    api: OpenAI,
    subject: str,
    kps: list[dict[str, Any]],
    batch: list[dict[str, Any]],
    retries: int,
) -> list[dict[str, Any]]:
    prompt = make_prompt(subject, kps, batch)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = api.chat.completions.create(
                model=settings.qwen_text_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=8000,
            )
            data = json_from_text(resp.choices[0].message.content or "")
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError(f"bad mapping length: {len(data) if isinstance(data, list) else type(data)}")
            return [x for x in data if isinstance(x, dict)]
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(1.5 + attempt)
    raise RuntimeError(str(last_error))


def existing_report() -> dict[str, Any]:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {
        "source": SOURCE,
        "model": settings.qwen_text_model,
        "processed": 0,
        "items": [],
        "errors": [],
        "generated_at": None,
    }


def normalize_item(raw: dict[str, Any], q: dict[str, Any], valid_ids: set[int], kp_meta: dict[int, dict[str, Any]]) -> dict[str, Any]:
    def to_id(value: Any) -> int | None:
        try:
            x = int(value)
        except (TypeError, ValueError):
            return None
        return x if x in valid_ids else None

    primary = to_id(raw.get("primary_knowledge_point_id"))
    related = []
    for value in raw.get("related_knowledge_point_ids") or []:
        x = to_id(value)
        if x is not None and x != primary and x not in related:
            related.append(x)
    related = related[:3]
    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    item = {
        "question_id": int(q["id"]),
        "subject": q["subject"],
        "question_type": q["question_type"],
        "stem": q["stem"],
        "primary_knowledge_point_id": primary,
        "related_knowledge_point_ids": related,
        "confidence": max(0.0, min(1.0, confidence)),
        "reason": str(raw.get("reason") or "").strip(),
    }
    if primary:
        kp = kp_meta[primary]
        item.update(
            {
                "chapter": kp["chapter"],
                "exam_point": kp["exam_point"],
                "knowledge_point": kp["knowledge_point"],
            }
        )
    return item


def run(batch_size: int, limit: int | None, retries: int) -> dict[str, Any]:
    c = conn()
    try:
        kps_by_subject = load_kps(c)
        questions = load_questions(c)
    finally:
        c.close()
    if limit:
        questions = questions[:limit]

    valid_by_subject = {s: {kp["id"] for kp in kps} for s, kps in kps_by_subject.items()}
    kp_meta = {kp["id"]: kp for kps in kps_by_subject.values() for kp in kps}
    report = existing_report()
    done_ids = {int(x["question_id"]) for x in report.get("items", [])}
    api = client()

    for subject in ["经济法", "中级会计实务", "财务管理"]:
        subject_questions = [q for q in questions if q.get("subject") == subject and int(q["id"]) not in done_ids]
        for offset in range(0, len(subject_questions), batch_size):
            batch = subject_questions[offset : offset + batch_size]
            try:
                mapped = map_batch(api, subject, kps_by_subject[subject], batch, retries)
                by_index = {int(x.get("index")): x for x in mapped if str(x.get("index", "")).isdigit()}
                for i, q in enumerate(batch):
                    raw = by_index.get(i, {})
                    item = normalize_item(raw, q, valid_by_subject[subject], kp_meta)
                    report["items"].append(item)
                    done_ids.add(int(q["id"]))
                report["processed"] = len(report["items"])
                report["generated_at"] = datetime.now().isoformat(timespec="seconds")
                OUT.parent.mkdir(parents=True, exist_ok=True)
                OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                mapped_count = sum(1 for x in report["items"] if x.get("primary_knowledge_point_id"))
                print(f"{subject} processed={report['processed']}/{len(questions)} mapped={mapped_count}", flush=True)
                time.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                err = {"subject": subject, "question_ids": [q["id"] for q in batch], "error": str(e)}
                report["errors"].append(err)
                OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"ERROR {err}", flush=True)
    return report


def backup_db() -> Path:
    dst = settings.db_path.with_suffix(f".db.bak-hqwx-semantic-map-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(settings.db_path, dst)
    return dst


def apply_report(min_confidence: float) -> dict[str, Any]:
    report = existing_report()
    items = report.get("items", [])
    mapping = {
        int(x["question_id"]): x
        for x in items
        if x.get("primary_knowledge_point_id") and float(x.get("confidence") or 0) >= min_confidence
    }
    backup = backup_db()
    c = conn()
    try:
        for qid, item in mapping.items():
            c.execute(
                """
                UPDATE questions
                SET knowledge_point_id = ?, chapter = ?, exam_point = ?, confidence = ?
                WHERE id = ? AND source = ?
                """,
                (
                    int(item["primary_knowledge_point_id"]),
                    item.get("chapter"),
                    item.get("exam_point"),
                    float(item.get("confidence") or 0),
                    qid,
                    SOURCE,
                ),
            )
        c.execute(
            """
            UPDATE questions
            SET knowledge_point_id = NULL, chapter = CASE
                    WHEN chapter IN ('经济法','中级会计实务','财务管理') THEN chapter
                    ELSE COALESCE((SELECT ep.subject FROM knowledge_points kp JOIN exam_points ep ON ep.id = kp.exam_point_id WHERE kp.id = questions.knowledge_point_id), chapter)
                END,
                exam_point = '待映射'
            WHERE source = ? AND id NOT IN ({})
            """.format(",".join("?" for _ in mapping) or "NULL"),
            (SOURCE, *mapping.keys()),
        )
        c.commit()
    finally:
        c.close()
    summary = {
        "backup": str(backup),
        "applied": len(mapping),
        "min_confidence": min_confidence,
        "report": str(OUT),
    }
    report["apply_summary"] = summary
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.55)
    args = parser.parse_args()
    if args.reset and OUT.exists():
        OUT.unlink()
    report = run(args.batch_size, args.limit, args.retries)
    mapped = sum(1 for x in report.get("items", []) if x.get("primary_knowledge_point_id"))
    summary = {
        "processed": report.get("processed"),
        "mapped": mapped,
        "errors": len(report.get("errors", [])),
        "report": str(OUT),
    }
    if args.apply:
        summary["apply"] = apply_report(args.min_confidence)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
