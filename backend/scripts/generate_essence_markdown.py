"""Generate draft essence markdown for syllabus knowledge points."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from openai import OpenAI

from app.config import PROJECT_ROOT, settings


HEADING_RE = re.compile(r"^##\s+(.+?)\s+`(.+?)`\s*$", re.MULTILINE)


def _client() -> OpenAI:
    return OpenAI(api_key=settings.dashscope_api_key, base_url=settings.dashscope_base_url)


def _chapter_text(chapters: list[tuple[int, dict]]) -> str:
    lines: list[str] = []
    for idx, chapter in chapters:
        lines.append(f"第{idx}章 {chapter['name']}")
        for section in chapter["sections"]:
            lines.append(f"- {section['name']}")
            for kp in section["knowledge_points"]:
                lines.append(f"  - {kp['name']} `{kp['mastery']}`")
    return "\n".join(lines)


def _expected(chapters: list[tuple[int, dict]]) -> list[tuple[str, str]]:
    return [
        (kp["name"], kp["mastery"])
        for _, chapter in chapters
        for section in chapter["sections"]
        for kp in section["knowledge_points"]
    ]


def _clean_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("markdown"):
            text = text[8:].strip()
    return text.rstrip() + "\n"


def generate_chunk(syllabus_path: Path, subject: str, start: int, end: int, out: Path) -> None:
    data = json.loads(syllabus_path.read_text(encoding="utf-8"))
    chapters = [
        (i + 1, chapter)
        for i, chapter in enumerate(data["chapters"])
        if start <= i + 1 <= end
    ]
    expected = _expected(chapters)
    prompt = f"""你是中级会计考试教研员。请为《{subject}》下列知识点编写可用于刷题命题的“知识点要义”Markdown。

硬性格式：
1. 文件第一行写：# {subject} 知识点要义 · 第{start}-{end}章
2. 每个知识点必须使用二级标题，格式严格为：## 知识点名 `掌握/熟悉/了解`
3. 标题中的知识点名和能力要求必须逐字照抄清单，不能增删改字。
4. 每个知识点正文 2-4 个短 bullet，写定义、确认/计量/公式/账务处理、常考易错点。
5. 不要编题，不要写寒暄，不要用 markdown 表格。
6. 内容要服务后续命题，尽量具体，避免空话。

知识点清单：
{_chapter_text(chapters)}
"""
    print(f"generating {out.name}: {len(expected)} knowledge points")
    resp = _client().chat.completions.create(
        model=settings.qwen_text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.25,
        max_tokens=12000,
    )
    text = _clean_markdown(resp.choices[0].message.content or "")
    got = HEADING_RE.findall(text)
    got_pairs = [(name.strip(), mastery.strip()) for name, mastery in got]
    missing = [pair for pair in expected if pair not in got_pairs]
    extra = [pair for pair in got_pairs if pair not in expected]
    if len(missing) == 1 and len(extra) == 1 and missing[0][1] == extra[0][1]:
        wrong = f"## {extra[0][0]} `{extra[0][1]}`"
        right = f"## {missing[0][0]} `{missing[0][1]}`"
        text = text.replace(wrong, right, 1)
        got = HEADING_RE.findall(text)
        got_pairs = [(name.strip(), mastery.strip()) for name, mastery in got]
        missing = [pair for pair in expected if pair not in got_pairs]
        extra = [pair for pair in got_pairs if pair not in expected]
    if missing or extra or len(got_pairs) != len(expected):
        print(f"validation failed: {out}")
        print("missing:", missing[:20], "count", len(missing))
        print("extra:", extra[:20], "count", len(extra))
        raise SystemExit(2)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["shiwu", "caiwu", "all"], default="all")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    data = PROJECT_ROOT / "data"
    chunks = []
    if args.only in {"shiwu", "all"}:
        chunks.extend(
            [
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    9,
                    11,
                    data / "knowledge-content-shiwu-ch9-11.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    12,
                    12,
                    data / "knowledge-content-shiwu-ch12.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    13,
                    13,
                    data / "knowledge-content-shiwu-ch13.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    14,
                    17,
                    data / "knowledge-content-shiwu-ch14-17.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    18,
                    18,
                    data / "knowledge-content-shiwu-ch18.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    19,
                    19,
                    data / "knowledge-content-shiwu-ch19.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    20,
                    20,
                    data / "knowledge-content-shiwu-ch20.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    21,
                    21,
                    data / "knowledge-content-shiwu-ch21.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    22,
                    22,
                    data / "knowledge-content-shiwu-ch22.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    23,
                    23,
                    data / "knowledge-content-shiwu-ch23.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    24,
                    24,
                    data / "knowledge-content-shiwu-ch24.md",
                ),
                (
                    data / "syllabus-shiwu-2026.json",
                    "中级会计实务",
                    25,
                    25,
                    data / "knowledge-content-shiwu-ch25.md",
                ),
            ]
        )
    if args.only in {"caiwu", "all"}:
        chunks.extend(
            [
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    1,
                    3,
                    data / "knowledge-content-caiwuguanli-ch1-3.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    4,
                    4,
                    data / "knowledge-content-caiwuguanli-ch4.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    5,
                    5,
                    data / "knowledge-content-caiwuguanli-ch5.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    6,
                    6,
                    data / "knowledge-content-caiwuguanli-ch6.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    7,
                    7,
                    data / "knowledge-content-caiwuguanli-ch7.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    8,
                    8,
                    data / "knowledge-content-caiwuguanli-ch8.md",
                ),
                (
                    data / "syllabus-caiwuguanli-2026.json",
                    "财务管理",
                    9,
                    10,
                    data / "knowledge-content-caiwuguanli-ch9-10.md",
                ),
            ]
        )
    for chunk in chunks:
        if args.skip_existing and chunk[-1].exists():
            print(f"skip existing {chunk[-1].name}")
            continue
        generate_chunk(*chunk)
        time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
