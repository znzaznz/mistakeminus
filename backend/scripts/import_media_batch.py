"""批量导入 media/ 目录下全部 PDF（增量，不清库）。

用法（backend 目录下）：
    python -m scripts.import_media_batch
    python -m scripts.import_media_batch --dir ../media
"""

from __future__ import annotations

import sys
from pathlib import Path

from app import db
from app.config import PROJECT_ROOT
from app.extraction import vlm
from app.extraction.importer import import_pdf


def main(argv: list[str]) -> int:
    media_dir = PROJECT_ROOT / "media"
    if "--dir" in argv:
        i = argv.index("--dir")
        media_dir = Path(argv[i + 1])

    pdfs = sorted(media_dir.glob("*.pdf"))
    if not pdfs:
        print(f"✗ {media_dir} 下没有 PDF")
        return 1

    db.init_db()
    conn = db.get_connection()
    conn.execute("PRAGMA busy_timeout = 60000")
    total_imported = total_pages = 0
    try:
        print(f"→ 共 {len(pdfs)} 份 PDF，开始 VLM 导入 …")
        for i, path in enumerate(pdfs, 1):
            print(f"\n[{i}/{len(pdfs)}] {path.name}")
            summary = import_pdf(path, extract_fn=vlm.extract_questions, conn=conn)
            print("  " + summary.describe())
            for err in summary.errors[:5]:
                print(f"    · {err}")
            total_imported += summary.imported
            total_pages += summary.pages
        print(
            f"\n✓ 全部完成：{len(pdfs)} 份 / {total_pages} 页 / "
            f"识别入库 {total_imported} 道题"
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
