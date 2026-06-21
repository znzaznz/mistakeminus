"""从 data/knowledge-content-jingjifa-ch*.md 载入知识点要义（S4）。

解析 `##` / `###` 标题中的知识点名与能力要求，正文作为 essence 写入库。
幂等：按知识点名匹配更新；已有 essence 且未传 --force 时跳过。

用法（backend 目录下）：
    python -m scripts.load_essence            # 只补空 essence
    python -m scripts.load_essence --force    # 覆盖全部
    python -m scripts.load_essence --dry      # 预演
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from app import db
from app.config import PROJECT_ROOT

_HEADING_RE = re.compile(
    r"^#{2,3}\s+(?:\d+\.\s+)?(.+?)\s+`(熟悉|掌握|了解)`\s*$",
    re.MULTILINE,
)


def _parse_md(text: str) -> list[tuple[str, str]]:
    """返回 [(知识点名, essence正文), ...]。"""
    items: list[tuple[str, str]] = []
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # 去掉节级 ## 标题块里嵌套的 ### 子标题前的空行噪音即可，正文保留
        if body:
            items.append((name, body))
    return items


def collect_essence_files(root: Path | None = None) -> list[Path]:
    # 三科要义文件：jingjifa / shiwu / caiwuguanli，均为 knowledge-content-<科目>-ch*.md
    data = root or (PROJECT_ROOT / "data")
    return sorted(data.glob("knowledge-content-*-ch*.md"))


def load_essence(
    conn: sqlite3.Connection,
    *,
    force: bool = False,
    dry: bool = False,
    data_dir: Path | None = None,
) -> dict:
    by_name: dict[str, str] = {}
    for path in collect_essence_files(data_dir):
        for name, body in _parse_md(path.read_text(encoding="utf-8")):
            by_name[name] = body  # 后文件覆盖同名（不应发生）

    updated = skipped = missing = 0
    for name, essence in by_name.items():
        row = conn.execute(
            "SELECT id, essence FROM knowledge_points WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            missing += 1
            continue
        if row["essence"] and not force:
            skipped += 1
            continue
        if not dry:
            conn.execute(
                "UPDATE knowledge_points SET essence = ? WHERE id = ?",
                (essence, row["id"]),
            )
        updated += 1
    if not dry:
        conn.commit()
    return {
        "parsed": len(by_name),
        "updated": updated,
        "skipped": skipped,
        "missing": missing,
    }


def main(argv: list[str]) -> int:
    force = "--force" in argv
    dry = "--dry" in argv
    db.init_db()
    conn = db.get_connection()
    try:
        s = load_essence(conn, force=force, dry=dry)
        tag = "[预演]" if dry else "[已写库]"
        print(
            f"{tag} 解析 {s['parsed']} 条要义；"
            f"写入 {s['updated']}，跳过已有 {s['skipped']}，"
            f"库中无匹配名 {s['missing']}。"
        )
        if s["missing"]:
            print("  [WARN] 有 md 中的知识点名在考纲种子中找不到，请核对命名。")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
