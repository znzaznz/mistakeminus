"""Full PDF question-bank extraction pipeline.

Pipeline:
1. Local VLM page collection: page image, content images, page candidates.
2. PDF text layer as the exact text source.
3. Cross-page question merge.
4. Answer/explanation pairing by question number.
5. Final JSON/Markdown plus a small alignment report.

Usage, from backend/:
    python -m scripts.extract_pdf_pipeline --downloads-glob "*280619*.pdf"
    python -m scripts.extract_pdf_pipeline path/to/file.pdf --out-dir ../output/pdf/run
    python -m scripts.extract_pdf_pipeline path/to/file.pdf --reuse-local-json path/to/result.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

import fitz

from app.extraction import pdf, vlm


ANSWER_MARKER = "参考答案"
CHROME_LINES = {
    "第一章",
    "总论",
    "| 强化班-刘琪",
    "学会计就到之了课堂",
}
SECTION_TITLES = {
    "代理行为",
    "仲裁",
    "民事诉讼",
    "易错易混",
}

Q_START = re.compile(r"^(\d+)\.【(.+?)·(\d{4})】")
OPTION_START = re.compile(r"^([A-D])\.(.*)")
ANSWER_RE = re.compile(r"(\d+)\.【答案】(.+?)\s*【解析】")


def _normalize(text: str) -> str:
    text = text.replace("\u2003", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def _is_chrome(line: str) -> bool:
    return line.isdigit() or line in CHROME_LINES


def _is_section(line: str) -> bool:
    return line in SECTION_TITLES or line.startswith("奇兵制胜") or line.endswith("考点")


def _answer_list(raw: str) -> list[str]:
    raw = _normalize(raw).replace(" ", "")
    if raw.isascii() and raw.isalpha():
        return list(raw)
    return [raw] if raw else []


def _latest_download(pattern: str) -> Path:
    matches = list((Path.home() / "Downloads").glob(pattern))
    if not matches:
        raise SystemExit(f"No PDF matched Downloads/{pattern}")
    return max(matches, key=lambda p: p.stat().st_mtime)


def collect_local_pages(pdf_path: Path, out_dir: Path) -> dict[str, Any]:
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            page_png = pdf.render_page_png(page, zoom=1.0)
            page_image = images_dir / f"page-{index:02d}.png"
            page_image.write_bytes(page_png)

            content_images: list[dict[str, Any]] = []
            for image_index, rect in enumerate(pdf.content_image_rects(page), start=1):
                cropped = pdf.crop_render_png(page, rect)
                if pdf.is_blank_png(cropped):
                    continue
                rel = Path("images") / f"page-{index:02d}-image-{image_index:02d}.png"
                (out_dir / rel).write_bytes(cropped)
                content_images.append(
                    {"path": rel.as_posix(), "bbox": [rect.x0, rect.y0, rect.x1, rect.y1]}
                )

            try:
                questions = vlm.extract_questions(page_png)
                error = None
            except Exception as exc:
                questions = []
                error = str(exc)

            pages.append(
                {
                    "page": index,
                    "page_image": f"images/{page_image.name}",
                    "content_images": content_images,
                    "questions": questions,
                    "error": error,
                }
            )
            print(f"page {index}/{len(doc)} candidates={len(questions)} images={len(content_images)} error={bool(error)}")

    result = {
        "source_pdf": str(pdf_path),
        "pages": len(pages),
        "question_count": sum(len(p["questions"]) for p in pages),
        "content_image_count": sum(len(p["content_images"]) for p in pages),
        "error_pages": [p["page"] for p in pages if p["error"]],
        "pages_detail": pages,
    }
    (out_dir / "01-local-ollama-full-candidates.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _copy_reused_images(local_root: Path, out_dir: Path) -> None:
    source = local_root / "images"
    target = out_dir / "images"
    target.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    for path in source.glob("*.png"):
        shutil.copy2(path, target / path.name)


def parse_questions(page_texts: dict[int, str], question_pages: list[int]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_option: dict[str, str] | None = None
    current_pages: set[int] = set()
    context: list[str] = []

    def flush_option() -> None:
        nonlocal current_option
        if current and current_option:
            current["options"].append(current_option)
        current_option = None

    def flush_question() -> None:
        nonlocal current, current_pages
        flush_option()
        if current:
            current["stem"] = _normalize(current["stem"])
            for option in current["options"]:
                option["text"] = _normalize(option["text"])
            current["source_pages"] = sorted(current_pages)
            questions.append(current)
        current = None
        current_pages = set()

    for page_no in question_pages:
        lines = [line.strip() for line in _normalize(page_texts[page_no]).splitlines() if line.strip()]
        for line in lines:
            if _is_chrome(line):
                continue
            if _is_section(line):
                context.append(line)
                continue

            q_match = Q_START.match(line)
            if q_match:
                flush_question()
                current = {
                    "number": int(q_match.group(1)),
                    "question_type": q_match.group(2),
                    "year": q_match.group(3),
                    "stem": line,
                    "options": [],
                    "context": context[-2:],
                }
                current_pages = {page_no}
                current_option = None
                continue

            if not current:
                continue
            current_pages.add(page_no)

            opt_match = OPTION_START.match(line)
            if opt_match:
                flush_option()
                current_option = {"key": opt_match.group(1), "text": opt_match.group(2)}
            elif current_option:
                current_option["text"] += line
            else:
                current["stem"] += line

    flush_question()
    return questions


def parse_answers(page_texts: dict[int, str], answer_pages: list[int]) -> dict[int, dict[str, Any]]:
    answer_text = _normalize("\n".join(page_texts[p] for p in answer_pages))
    matches = list(ANSWER_RE.finditer(answer_text))
    answers: dict[int, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(answer_text)
        answers[number] = {
            "number": number,
            "correct_answer": _answer_list(match.group(2)),
            "explanation": _normalize(answer_text[start:end]),
            "source_pages": answer_pages,
        }
    return answers


def build_result(pdf_path: Path, local: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    with fitz.open(pdf_path) as doc:
        page_texts = {index + 1: page.get_text() for index, page in enumerate(doc)}

    answer_start = next((p for p, text in page_texts.items() if ANSWER_MARKER in text), None)
    if answer_start is None:
        raise SystemExit("No reference-answer page found")

    question_pages = list(range(1, answer_start))
    answer_pages = list(range(answer_start, len(page_texts) + 1))
    questions = parse_questions(page_texts, question_pages)
    answers = parse_answers(page_texts, answer_pages)
    local_pages = {p["page"]: p for p in local["pages_detail"]}

    final_questions: list[dict[str, Any]] = []
    for question in questions:
        prefix = f"{question['number']}.【{question['question_type']}·{question['year']}】"
        candidate_pages: list[int] = []
        for page_no in question_pages:
            for candidate in local_pages.get(page_no, {}).get("questions", []):
                if (candidate.get("stem") or "").startswith(prefix):
                    candidate_pages.append(page_no)
        if candidate_pages:
            question["local_candidate_pages"] = sorted(set(candidate_pages))

        answer = answers.get(question["number"])
        expected_options = 0 if question["question_type"] == "判断" else 4
        issues: list[str] = []
        if len(question["options"]) != expected_options:
            issues.append(f"options {len(question['options'])}/{expected_options}")
        if not answer:
            issues.append("missing answer/explanation pair")

        final_questions.append(
            {
                **question,
                "correct_answer": answer["correct_answer"] if answer else [],
                "explanation": answer["explanation"] if answer else "",
                "answer_source_pages": answer["source_pages"] if answer else None,
                "needs_review": bool(issues),
                "review_reason": "; ".join(issues) if issues else None,
                "source": "PDF pipeline",
            }
        )

    evidence_images: list[dict[str, Any]] = []
    for page_no in question_pages:
        page = local_pages.get(page_no, {})
        if page.get("page_image"):
            evidence_images.append({"page": page_no, "type": "page_image", "path": f"images/{Path(page['page_image']).name}"})
        for image in page.get("content_images", []):
            evidence_images.append(
                {
                    "page": page_no,
                    "type": "lecture_or_content_image",
                    "path": f"images/{Path(image['path']).name}",
                    "bbox": image["bbox"],
                }
            )

    result = {
        "source_pdf": str(pdf_path),
        "question_pages": question_pages,
        "answer_pages": answer_pages,
        "pipeline": [
            "local Ollama full-page candidates collected first",
            "PDF text layer used to recover exact visible text",
            "question parser merges text across page boundaries",
            "answers/explanations paired by question number from reference answer pages",
            "final JSON keeps source pages, answer source pages, image evidence, and review flags",
        ],
        "question_count": len(final_questions),
        "matched_answer_count": sum(bool(q["correct_answer"]) for q in final_questions),
        "review_count": sum(bool(q["needs_review"]) for q in final_questions),
        "questions": final_questions,
        "evidence_images": evidence_images,
    }

    (out_dir / "02-question-text-layer.txt").write_text(
        "\n\n".join(f"===== PAGE {p} =====\n{page_texts[p]}" for p in question_pages),
        encoding="utf-8",
    )
    (out_dir / "03-answer-text-layer.txt").write_text(
        "\n\n".join(f"===== PAGE {p} =====\n{page_texts[p]}" for p in answer_pages),
        encoding="utf-8",
    )
    (out_dir / "04-merged-questions-before-answers.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "05-answer-pairs.json").write_text(
        json.dumps(answers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def write_reports(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "final-question-bank.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# Full PDF Pipeline Result",
        "",
        f"PDF: {Path(result['source_pdf']).name}",
        f"Questions: {result['question_count']}",
        f"Answers matched: {result['matched_answer_count']}",
        f"Needs review: {result['review_count']}",
        "",
        "## Questions",
    ]
    for q in result["questions"]:
        md += [f"### {q['number']}. {q['question_type']} {q['year']}", q["stem"]]
        md += [f"- {opt['key']}. {opt['text']}" for opt in q.get("options", [])]
        md.append(f"answer: {''.join(q.get('correct_answer', [])) or '(empty)'}")
        md.append(f"question_pages: {q['source_pages']} | answer_pages: {q['answer_source_pages']} | needs_review: {q['needs_review']}")
        if q.get("review_reason"):
            md.append(f"review_reason: {q['review_reason']}")
        if q.get("explanation"):
            suffix = "..." if len(q["explanation"]) > 500 else ""
            md.append("explanation: " + q["explanation"][:500] + suffix)
        md.append("")
    (out_dir / "final-question-bank.md").write_text("\n".join(md), encoding="utf-8")

    rows = []
    for q in result["questions"]:
        expected_options = 0 if q["question_type"] == "判断" else 4
        ok = (
            len(q.get("options", [])) == expected_options
            and bool(q.get("correct_answer"))
            and bool(q.get("explanation"))
            and not q.get("needs_review")
        )
        rows.append(
            {
                "number": q["number"],
                "options_count": len(q.get("options", [])),
                "expected_options": expected_options,
                "answer": "".join(q.get("correct_answer", [])),
                "has_explanation": bool(q.get("explanation")),
                "question_pages": q.get("source_pages"),
                "answer_pages": q.get("answer_source_pages"),
                "ok": ok,
                "review_reason": q.get("review_reason"),
            }
        )
    (out_dir / "alignment-check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Alignment Check",
        "",
        f"- question_count: {len(result['questions'])}",
        f"- matched_answer_count: {result['matched_answer_count']}",
        f"- review_count: {result['review_count']}",
        f"- evidence_images: {len(result['evidence_images'])}",
        f"- ok_count: {sum(row['ok'] for row in rows)}",
        "",
    ]
    for row in rows:
        report.append(
            f"- Q{row['number']}: {'OK' if row['ok'] else 'CHECK'} | "
            f"options={row['options_count']}/{row['expected_options']} | "
            f"answer={row['answer']} | explanation={row['has_explanation']} | "
            f"q_pages={row['question_pages']} | a_pages={row['answer_pages']}"
        )
        if row["review_reason"]:
            report.append(f"  reason: {row['review_reason']}")
    (out_dir / "alignment-check.md").write_text("\n".join(report), encoding="utf-8")

    write_complete_package(result, out_dir)


def _parse_page_dump(text_blob: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text_blob.splitlines():
        match = re.match(r"^===== PAGE (\d+) =====$", line.strip())
        if match:
            if current:
                pages.append(current)
            current = {"page": int(match.group(1)), "lines": []}
        elif current is not None:
            current["lines"].append(line)
    if current:
        pages.append(current)
    return pages


def write_complete_package(result: dict[str, Any], out_dir: Path) -> None:
    """Write the full document package: pages, lecture text/images, questions, answers."""
    question_dump = (out_dir / "02-question-text-layer.txt").read_text(encoding="utf-8")
    answer_dump = (out_dir / "03-answer-text-layer.txt").read_text(encoding="utf-8")
    question_pages = _parse_page_dump(question_dump)
    answer_pages = _parse_page_dump(answer_dump)

    questions_by_page: dict[int, list[int]] = {}
    continuation_pages: set[int] = set()
    for question in result["questions"]:
        source_pages = question.get("source_pages") or []
        for page_no in source_pages:
            questions_by_page.setdefault(page_no, []).append(question["number"])
        for page_no in source_pages[1:]:
            continuation_pages.add(page_no)

    images_by_page: dict[int, list[dict[str, Any]]] = {}
    for image in result.get("evidence_images", []):
        images_by_page.setdefault(image["page"], []).append(image)

    page_records: list[dict[str, Any]] = []
    lecture_blocks: list[dict[str, Any]] = []
    current_section: str | None = None

    for page in question_pages:
        page_no = page["page"]
        raw_lines = [_normalize(line) for line in page["lines"]]
        clean_lines = [line for line in raw_lines if not _is_chrome(line)]
        lecture_lines: list[str] = []
        in_question = False
        seen_question = False

        for line in clean_lines:
            if _is_section(line):
                in_question = False
                current_section = line
                lecture_lines.append(line)
                continue
            if Q_START.match(line):
                in_question = True
                seen_question = True
                continue
            if page_no in continuation_pages and not seen_question:
                continue
            if in_question:
                continue
            if OPTION_START.match(line) or ANSWER_RE.match(line):
                continue
            lecture_lines.append(line)

        lecture_text = "\n".join(line for line in lecture_lines if line).strip()
        page_images = images_by_page.get(page_no, [])
        content_images = [image for image in page_images if image.get("type") != "page_image"]
        if lecture_text or content_images:
            lecture_blocks.append(
                {
                    "page": page_no,
                    "section": current_section,
                    "text": lecture_text,
                    "images": content_images,
                }
            )
        page_records.append(
            {
                "page": page_no,
                "raw_text": "\n".join(raw_lines).strip(),
                "lecture_text": lecture_text,
                "question_numbers": questions_by_page.get(page_no, []),
                "images": page_images,
            }
        )

    answer_records: list[dict[str, Any]] = []
    for page in answer_pages:
        numbers: list[int] = []
        for line in page["lines"]:
            match = ANSWER_RE.match(_normalize(line))
            if match:
                numbers.append(int(match.group(1)))
        answer_records.append(
            {
                "page": page["page"],
                "raw_text": "\n".join(page["lines"]).strip(),
                "answer_numbers_starting_here": numbers,
            }
        )

    questions: list[dict[str, Any]] = []
    for question in result["questions"]:
        candidate_images: list[dict[str, Any]] = []
        for page_no in question.get("source_pages") or []:
            candidate_images.extend(
                image for image in images_by_page.get(page_no, []) if image.get("type") != "page_image"
            )
        questions.append({**question, "candidate_images_on_source_pages": candidate_images})

    package = {
        "source_pdf": result["source_pdf"],
        "summary": {
            "question_count": len(questions),
            "lecture_block_count": len(lecture_blocks),
            "question_page_count": len(question_pages),
            "answer_page_count": len(answer_pages),
            "image_evidence_count": len(result.get("evidence_images", [])),
        },
        "pages": page_records,
        "lecture_blocks": lecture_blocks,
        "questions": questions,
        "answer_pages": answer_records,
    }
    (out_dir / "complete-document-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# Complete Document Package",
        "",
        f"PDF: {Path(result['source_pdf']).name}",
        "",
        "## Summary",
    ]
    for key, value in package["summary"].items():
        md.append(f"- {key}: {value}")
    md += ["", "## Lecture Blocks"]
    for block in lecture_blocks:
        md.append(f"### Page {block['page']} | {block.get('section') or ''}")
        if block["text"]:
            md.append(block["text"])
        if block["images"]:
            md.append("Images: " + ", ".join(image["path"] for image in block["images"]))
        md.append("")
    md += ["", "## Questions"]
    for question in questions:
        md.append(f"### Q{question['number']} {question['question_type']} {question['year']}")
        md.append(question["stem"])
        for option in question.get("options", []):
            md.append(f"- {option['key']}. {option['text']}")
        md.append("answer: " + "".join(question.get("correct_answer", [])))
        md.append(
            f"question_pages: {question.get('source_pages')} | "
            f"answer_pages: {question.get('answer_source_pages')}"
        )
        if question["candidate_images_on_source_pages"]:
            md.append(
                "candidate images: "
                + ", ".join(image["path"] for image in question["candidate_images_on_source_pages"])
            )
        md.append("")
    (out_dir / "complete-document-package.md").write_text("\n".join(md), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--downloads-glob", help="Find the newest matching PDF in Downloads, avoids Chinese path quoting issues")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--reuse-local-json", type=Path, help="Reuse a previous local Ollama collection result.json")
    args = parser.parse_args(argv)

    if args.downloads_glob:
        pdf_path = _latest_download(args.downloads_glob)
    elif args.pdf:
        pdf_path = args.pdf
    else:
        raise SystemExit("Provide a PDF path or --downloads-glob")

    pdf_path = pdf_path.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    out_dir = (args.out_dir or (Path.home() / "Downloads" / f"{pdf_path.stem}-full-pipeline")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.reuse_local_json:
        local_json = args.reuse_local_json.resolve()
        local = json.loads(local_json.read_text(encoding="utf-8"))
        (out_dir / "01-local-ollama-full-candidates.json").write_text(
            json.dumps(local, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _copy_reused_images(local_json.parent, out_dir)
    else:
        local = collect_local_pages(pdf_path, out_dir)

    result = build_result(pdf_path, local, out_dir)
    write_reports(result, out_dir)
    print(out_dir)
    print(
        f"questions={result['question_count']} "
        f"answers={result['matched_answer_count']} "
        f"review={result['review_count']} "
        f"images={len(result['evidence_images'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
