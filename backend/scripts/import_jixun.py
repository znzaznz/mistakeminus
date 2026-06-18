"""计划 A：客观题集训 PDF 导入（文本解析，不走 VLM）。

用法（backend 目录下）：
    python -m scripts.import_jixun --dry              # 校验三份，输出抽查样本
    python -m scripts.import_jixun --dry --limit 10   # 多抽查几题
    python -m scripts.import_jixun                    # 备份 DB 后入库
    python -m scripts.import_jixun --no-backup        # 跳过备份（不推荐）

默认读取 media/*客观题集训*.pdf（3 份）。
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from app import db
from app.config import PROJECT_ROOT, settings
from app.extraction.jixun import parse_jixun_pdf, sample_lines

SOURCE_PREFIX = "集训-周周"


def _jixun_pdfs(media_dir: Path | None = None) -> list[Path]:
    root = media_dir or (PROJECT_ROOT / "media")
    return sorted(root.glob("*客观题集训*.pdf"))


def _backup_db() -> Path:
    src = settings.db_path
    dst = src.with_suffix(f".db.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(src, dst)
    return dst


def _insert_draft(conn, draft, *, pdf_name: str, qnum: int) -> None:
    conn.execute(
        """
        INSERT INTO questions
            (chapter, exam_point, question_type, stem, options,
             correct_answer, explanation, images, source, source_ref,
             confidence, needs_review)
        VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, 1.0, 0)
        """,
        (
            draft.chapter,
            draft.exam_point,
            draft.question_type,
            draft.stem,
            json.dumps([o.model_dump() for o in draft.options], ensure_ascii=False),
            json.dumps(draft.correct_answer, ensure_ascii=False),
            draft.explanation,
            f"{SOURCE_PREFIX}-{draft.chapter or '未知'}",
            f"{pdf_name}#q={qnum}",
        ),
    )


def _remove_prior_jixun(conn) -> int:
    cur = conn.execute(
        "DELETE FROM questions WHERE source LIKE ?",
        (f"{SOURCE_PREFIX}-%",),
    )
    return cur.rowcount


def _remove_vlm_media_pollution(conn) -> int:
    """清掉误用 VLM 导入 media/ 讲义产生的题目（计划 A 前误跑）。"""
    rows = conn.execute("SELECT id, source_ref FROM questions WHERE source = 'PDF导入'").fetchall()
    media_names = {p.name for p in (PROJECT_ROOT / "media").glob("*.pdf")}
    ids = [r["id"] for r in rows if r["source_ref"] and r["source_ref"].split("#")[0] in media_names]
    if not ids:
        return 0
    conn.execute(f"DELETE FROM questions WHERE id IN ({','.join('?' * len(ids))})", ids)
    return len(ids)


def dry_run(pdfs: list[Path], limit: int) -> bool:
    all_ok = True
    for path in pdfs:
        print(f"\n=== {path.name} ===")
        report = parse_jixun_pdf(path)
        print(f"  章：{report.chapter}")
        print(f"  题目 {report.question_count} / 答案 {report.answer_count}")
        print(f"  题号连续：{report.continuous}")
        if report.missing_in_answers:
            print(f"  [WARN] 题无答案：{report.missing_in_answers[:10]}")
        if report.missing_in_questions:
            print(f"  [WARN] 答案无题：{report.missing_in_questions[:10]}")
        for err in report.errors[:5]:
            print(f"  [ERR] {err}")
        print("  --- 抽查 ---")
        for line in sample_lines(report, limit):
            print(f"  {line}")
        if not report.ok:
            all_ok = False
            print("  [FAIL] 校验未通过，停止")
        else:
            print("  [OK] 校验通过")
    return all_ok


def import_all(pdfs: list[Path], *, backup: bool) -> int:
    if backup:
        bak = _backup_db()
        print(f"→ 已备份 DB：{bak.name}")

    db.init_db()
    conn = db.get_connection()
    try:
        removed_vlm = _remove_vlm_media_pollution(conn)
        removed_old = _remove_prior_jixun(conn)
        if removed_vlm or removed_old:
            print(f"→ 清理旧数据：VLM误导入 {removed_vlm} 条，旧集训 {removed_old} 条")

        total = 0
        for path in pdfs:
            report = parse_jixun_pdf(path)
            if not report.ok:
                raise RuntimeError(f"{path.name} 校验未通过，拒绝入库")
            for i, draft in enumerate(report.drafts, start=1):
                _insert_draft(conn, draft, pdf_name=path.name, qnum=i)
            total += len(report.drafts)
            print(f"  [OK] {path.name}：入库 {len(report.drafts)} 道（{report.chapter}）")
        conn.commit()
        print(f"\n[OK] 集训导入完成，共 {total} 道可练题")
        return total
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    backup = "--no-backup" not in argv
    limit = 5
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])

    pdfs = _jixun_pdfs()
    if not pdfs:
        print("[ERR] 未找到 media/*客观题集训*.pdf")
        return 1

    print(f"→ 找到 {len(pdfs)} 份集训 PDF")
    if dry:
        ok = dry_run(pdfs, limit)
        return 0 if ok else 1

    if not dry_run(pdfs, limit):
        print("\n[FAIL] dry 校验未全部通过，已中止入库")
        return 1

    try:
        import_all(pdfs, backup=backup)
    except RuntimeError as e:
        print(f"[FAIL] {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
