"""Map IDEAFinBench CPA candidates to local subject knowledge points."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings


ROOT = Path.home() / "Downloads" / "needreadfile_output"
SOURCE = "DataArcTech/IDEAFinBench"
SUBJECTS = {
    "shiwu": {
        "cpa": "accounting",
        "local_subject": "中级会计实务",
        "out": ROOT / "_ideafinbench_accounting_candidate_mapping.json",
    },
    "caiwu": {
        "cpa": "financial_management",
        "local_subject": "财务管理",
        "out": ROOT / "_ideafinbench_financial_management_candidate_mapping.json",
    },
}


def _client() -> OpenAI:
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)


def _rows(cpa_subject: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in ["cpa_one", "cpa_multi"]:
        for split in ["dev", "val"]:
            url = (
                "https://raw.githubusercontent.com/DataArcTech/IDEAFinBench/main/"
                f"datasets/{kind}/{split}/{cpa_subject}_{split}.csv"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Codex"})
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8-sig")
            for row in csv.DictReader(io.StringIO(text)):
                row["_kind"] = kind
                row["_split"] = split
                row["_source_url"] = url
                rows.append(row)
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        seen[(row["question"].strip(), row.get("answer", "").strip(), row["_kind"])] = row
    return list(seen.values())


def _kp_rows(conn: sqlite3.Connection, subject: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT kp.id, ep.chapter, ep.name AS exam_point, kp.name AS knowledge_point
            FROM knowledge_points kp
            JOIN exam_points ep ON ep.id = kp.exam_point_id
            WHERE ep.subject = ?
            ORDER BY ep.seq, kp.seq
            """,
            (subject,),
        )
    ]


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


def _map_batch(client: OpenAI, local_subject: str, kps: list[dict[str, Any]], batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kp_text = "\n".join(
        f"{kp['id']} | {kp['chapter']} | {kp['exam_point']} | {kp['knowledge_point']}"
        for kp in kps
    )
    q_text = "\n".join(
        f"{i}. {row['question']}\nA. {row.get('A','')}\nB. {row.get('B','')}\nC. {row.get('C','')}\nD. {row.get('D','')}"
        for i, row in enumerate(batch)
    )
    prompt = f"""你要把 CPA 题源候选题映射到《{local_subject}》的中级会计知识点。

只在题目明确属于某个知识点时给 knowledge_point_id；不确定、CPA 超纲、或多个点都像时填 null。
不要为了覆盖率强行映射。输出严格 JSON 数组，长度必须等于题目数，格式：
[{{"index":0,"knowledge_point_id":123,"confidence":0.82,"reason":"..."}}]

知识点清单：
{kp_text}

题目：
{q_text}
"""
    resp = client.chat.completions.create(
        model=settings.qwen_text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=6000,
    )
    data = _json_from_text(resp.choices[0].message.content or "")
    if not isinstance(data, list):
        raise ValueError("mapping result is not a JSON array")
    return [x for x in data if isinstance(x, dict)]


def run(subject_key: str, *, batch_size: int, limit: int | None) -> dict[str, Any]:
    spec = SUBJECTS[subject_key]
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        kps = _kp_rows(conn, spec["local_subject"])
    finally:
        conn.close()
    valid_ids = {kp["id"] for kp in kps}
    kp_meta = {kp["id"]: kp for kp in kps}
    rows = _rows(spec["cpa"])
    if limit:
        rows = rows[:limit]

    out = spec["out"]
    if out.exists():
        report = json.loads(out.read_text(encoding="utf-8"))
        items: list[dict[str, Any]] = report.get("items", [])
        start = int(report.get("processed_rows", len(items)))
    else:
        report = {
            "source": SOURCE,
            "cpa_subject": spec["cpa"],
            "local_subject": spec["local_subject"],
            "raw_answered_rows": len(rows),
            "processed_rows": 0,
            "items": [],
            "errors": [],
        }
        items = report["items"]
        start = 0

    client = _client()
    for offset in range(start, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        try:
            mapped = _map_batch(client, spec["local_subject"], kps, batch)
            by_index = {int(x.get("index")): x for x in mapped if str(x.get("index", "")).isdigit()}
            for i, row in enumerate(batch):
                m = by_index.get(i, {})
                kp_id = m.get("knowledge_point_id")
                if kp_id is not None:
                    try:
                        kp_id = int(kp_id)
                    except (TypeError, ValueError):
                        kp_id = None
                if kp_id not in valid_ids:
                    kp_id = None
                item = {
                    "question": row["question"],
                    "A": row.get("A"),
                    "B": row.get("B"),
                    "C": row.get("C"),
                    "D": row.get("D"),
                    "answer": row.get("answer"),
                    "explanation": row.get("explanation", ""),
                    "question_type": "多选" if row["_kind"] == "cpa_multi" else "单选",
                    "source": SOURCE,
                    "source_url": row["_source_url"],
                    "knowledge_point_id": kp_id,
                    "mapping_confidence": m.get("confidence"),
                    "mapping_reason": m.get("reason"),
                }
                if kp_id is not None:
                    item.update(kp_meta[kp_id])
                items.append(item)
            report["processed_rows"] = len(items)
            mapped_count = sum(1 for x in items if x.get("knowledge_point_id"))
            print(f"{subject_key} {report['processed_rows']}/{len(rows)} mapped={mapped_count}")
        except Exception as e:
            report["errors"].append({"offset": offset, "error": str(e)})
            print(f"{subject_key} offset {offset} failed: {e}")
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.5)

    counts: dict[str, int] = {}
    for item in items:
        kp_id = item.get("knowledge_point_id")
        if kp_id:
            counts[str(kp_id)] = counts.get(str(kp_id), 0) + 1
    report["mapped_candidates"] = sum(1 for x in items if x.get("knowledge_point_id"))
    report["mapped_kp_count"] = len(counts)
    report["counts_by_kp"] = counts
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=["shiwu", "caiwu", "all"], default="all")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    keys = ["shiwu", "caiwu"] if args.subject == "all" else [args.subject]
    for key in keys:
        result = run(key, batch_size=args.batch_size, limit=args.limit)
        print(
            json.dumps(
                {
                    "subject": key,
                    "processed_rows": result["processed_rows"],
                    "mapped_candidates": result.get("mapped_candidates"),
                    "mapped_kp_count": result.get("mapped_kp_count"),
                    "errors": result["errors"][-3:],
                    "report": str(SUBJECTS[key]["out"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
