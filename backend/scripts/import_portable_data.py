"""从 data/imports/*.jsonl 重建 SQLite 题库数据（export_portable_data 的逆操作）。

用法：
  python -m scripts.import_portable_data           # 仅载入当前为空的表（幂等）
  python -m scripts.import_portable_data --force    # 先清空 4 张数据表再重灌

启动时 app 会自动对空表执行同样的重建（见 db.init_db → seed_from_snapshot），
本脚本用于手动重建或在 jsonl 更新后强制刷新本地库。
"""

from __future__ import annotations

import sys

from app import db


def main() -> int:
    force = "--force" in sys.argv
    db.init_db()  # 建表 + 对空表自动 seed
    conn = db.get_connection()
    try:
        if force:
            # 倒序删除以满足外键依赖
            for table in reversed(db.SNAPSHOT_TABLES):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
            loaded = db.seed_from_snapshot(conn)
        else:
            loaded = db.seed_from_snapshot(conn)
        if loaded:
            for table, n in loaded.items():
                print(f"{table}: {n}")
        else:
            print("所有数据表已有数据，未重新载入（用 --force 强制重灌）。")
        for table in db.SNAPSHOT_TABLES:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  现有 {table}: {cnt}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
