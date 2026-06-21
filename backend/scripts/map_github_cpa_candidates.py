"""Map public GitHub CPA economic-law candidates to local knowledge points."""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import urllib.request
from pathlib import Path

from app.config import settings


ROOT = Path.home() / "Downloads" / "needreadfile_output"
OUT = ROOT / "_github_cpa_economic_law_candidate_mapping.json"
SOURCE = "DataArcTech/IDEAFinBench"


def _rows() -> list[dict]:
    rows: list[dict] = []
    for kind in ["cpa_one", "cpa_multi"]:
        for split in ["dev", "val"]:
            url = (
                "https://raw.githubusercontent.com/DataArcTech/IDEAFinBench/main/"
                f"datasets/{kind}/{split}/economic_law_{split}.csv"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Codex"})
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8-sig")
            for row in csv.DictReader(io.StringIO(text)):
                row["_kind"] = kind
                row["_split"] = split
                row["_source_url"] = url
                rows.append(row)
    seen: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        seen[(row["question"].strip(), row.get("answer", "").strip(), row["_kind"])] = row
    return list(seen.values())


def _has(s: str, *xs: str) -> bool:
    return any(x in s for x in xs)


def _pick_kp(question: str) -> int | None:
    s = re.sub(r"\s+", "", question)
    if _has(s, "股东代表诉讼", "股东诉讼"):
        return 22
    if _has(s, "董事", "监事", "高级管理人员", "忠实义务", "勤勉义务"):
        return 21
    if _has(s, "股权转让", "优先购买权", "股东资格"):
        return 15
    if _has(s, "有限责任公司", "股东会", "董事会", "监事会", "经理"):
        return 14
    if _has(s, "股份有限公司", "发起人", "创立大会", "股份转让"):
        return 16
    if _has(s, "上市公司", "独立董事"):
        return 18
    if _has(s, "公司债券", "债券持有人"):
        return 24
    if _has(s, "股份发行", "股票发行", "股份回购"):
        return 23
    if _has(s, "利润分配", "公积金", "财务会计"):
        return 26
    if _has(s, "合并", "分立"):
        return 27
    if _has(s, "增资", "减资"):
        return 28
    if _has(s, "解散", "清算"):
        return 29
    if _has(s, "公司登记", "营业执照", "登记机关"):
        return 12
    if _has(s, "公司法人财产权"):
        return 11
    if _has(s, "公司法"):
        return 10
    if _has(s, "票据", "汇票", "本票", "支票", "背书", "承兑", "保证人", "追索权"):
        if _has(s, "本票"):
            return 92
        if _has(s, "支票"):
            return 93
        if _has(s, "汇票", "承兑", "背书", "追索"):
            return 91
        return 90
    if _has(s, "证券", "股票上市", "信息披露", "上市公司收购", "公开发行", "非公开发行"):
        if _has(s, "收购"):
            return 98
        if _has(s, "信息披露"):
            return 99
        if _has(s, "发行"):
            return 96
        if _has(s, "交易", "内幕交易", "操纵"):
            return 97
        return 95
    if _has(s, "国有资产", "国家出资企业", "产权登记", "资产评估", "企业资产转让", "国有股权"):
        return 109
    if _has(s, "预算"):
        return 103
    if _has(s, "政府采购"):
        return 111
    if _has(s, "保证合同", "保证期间"):
        return 87
    if _has(s, "买卖合同", "所有权保留", "标的物"):
        return 84
    if _has(s, "租赁合同", "承租人", "出租人"):
        return 88
    if _has(s, "借款合同", "借款人", "贷款人"):
        return 86
    if _has(s, "赠与合同", "赠与人"):
        return 85
    if _has(s, "抵押权", "抵押财产", "抵押合同"):
        return 55
    if _has(s, "质权", "质押"):
        return 56
    if _has(s, "留置权"):
        return 57
    if _has(s, "普通合伙"):
        return 30
    if _has(s, "有限合伙"):
        return 36
    if _has(s, "仲裁"):
        return 6
    if _has(s, "诉讼时效", "民事诉讼", "管辖"):
        return 7
    return None


def main() -> int:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    kp_rows = {
        r["id"]: dict(r)
        for r in conn.execute(
            """
            SELECT kp.id, kp.name knowledge_point, ep.name exam_point, ep.chapter
            FROM knowledge_points kp JOIN exam_points ep ON ep.id=kp.exam_point_id
            """
        )
    }
    covered = {
        r["knowledge_point_id"]
        for r in conn.execute("SELECT DISTINCT knowledge_point_id FROM questions WHERE knowledge_point_id IS NOT NULL")
    }
    items = []
    for row in _rows():
        kp_id = _pick_kp(row["question"])
        if not kp_id or kp_id not in kp_rows:
            continue
        meta = kp_rows[kp_id]
        items.append(
            {
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
                **meta,
                "fills_current_gap": kp_id not in covered,
            }
        )
    counts: dict[int, int] = {}
    for item in items:
        counts[item["knowledge_point_id"]] = counts.get(item["knowledge_point_id"], 0) + 1
    OUT.write_text(
        json.dumps(
            {
                "source": SOURCE,
                "raw_answered_rows": len(_rows()),
                "mapped_candidates": len(items),
                "mapped_kp_count": len(counts),
                "gap_kp_count": sum(1 for kp_id in counts if kp_id not in covered),
                "counts_by_kp": counts,
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "raw_answered_rows": len(_rows()),
                "mapped_candidates": len(items),
                "mapped_kp_count": len(counts),
                "gap_kp_count": sum(1 for kp_id in counts if kp_id not in covered),
                "report": str(OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
