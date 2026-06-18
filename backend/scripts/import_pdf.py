"""离线 PDF 题库导入脚本（S1）。

用法（在 backend 目录下，已激活 venv）：
    python -m scripts.import_pdf "../刘琪老师-....pdf"
    python -m scripts.import_pdf ../a.pdf ../b.pdf      # 可一次多份

需要 .env 里配好 DASHSCOPE_API_KEY（真实调用视觉模型）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import db
from app.config import settings
from app.extraction import vlm
from app.extraction.importer import import_pdf


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    if not settings.dashscope_api_key.strip():
        print("✗ 未配置 DASHSCOPE_API_KEY，请先在 .env 填入 key。")
        return 1

    db.init_db()
    conn = db.get_connection()
    try:
        for raw_path in argv:
            path = Path(raw_path)
            if not path.exists():
                print(f"✗ 找不到文件: {path}")
                continue
            print(f"→ 正在导入 {path.name} …")
            summary = import_pdf(path, extract_fn=vlm.extract_questions, conn=conn)
            print("  " + summary.describe())
            for err in summary.errors[:10]:
                print(f"    · {err}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
