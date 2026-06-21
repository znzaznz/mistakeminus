"""Generic PDF document package extraction with local page VLM collection.

This handles mixed files: question PDFs, lecture PDFs, image-like review PDFs.
It always preserves full page text/images and local VLM page candidates. When a
reference-answer section exists, it also writes a question-bank view.
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
CHROME_LINES = {"第一章", "总论", "| 强化班-刘琪", "学会计就到之了课堂"}
SECTION_TITLES = {"代理行为", "仲裁", "民事诉讼", "易错易混", "法律体系", "法律行为"}
Q_START = re.compile(r"^(\d+)\.【(.+?)·(\d{4})】")
OPTION_START = re.compile(r"^([A-D])\.(.*)")
ANSWER_RE = re.compile(r"(\d+)\.【答案】(.+?)\s*【解析】")


def normalize(text: str) -> str:
    text = text.replace("\u2003", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def slug_name(path: Path) -> str:
    stem = re.sub(r"[^\w.-]+", "_", path.stem, flags=re.UNICODE).strip("_")
    return stem[:90] or "pdf"


def is_chrome(line: str) -> bool:
    return line.isdigit() or line in CHROME_LINES


def is_section(line: str) -> bool:
    return line in SECTION_TITLES or line.startswith("奇兵制胜") or line.endswith("考点")


def answer_list(raw: str) -> list[str]:
    raw = normalize(raw).replace(" ", "")
    if raw.isascii() and raw.isalpha():
        return list(raw)
    return [raw] if raw else []


def collect_pages(
    pdf_path: Path,
    out_dir: Path,
    *,
    resume: bool = True,
    vlm_mode: str = "smart",
    text_threshold: int = 160,
) -> dict[str, Any]:
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    local_json = out_dir / "01-local-ollama-full-candidates.json"
    partial_jsonl = out_dir / "01-local-ollama-pages.partial.jsonl"
    if resume and local_json.exists():
        return json.loads(local_json.read_text(encoding="utf-8"))

    pages: list[dict[str, Any]] = []
    if resume and partial_jsonl.exists():
        for line in partial_jsonl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                pages.append(json.loads(line))

    with fitz.open(pdf_path) as doc:
        start_index = len(pages) + 1
        for index in range(start_index, len(doc) + 1):
            page = doc[index - 1]
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
                content_images.append({"path": rel.as_posix(), "bbox": [rect.x0, rect.y0, rect.x1, rect.y1]})

            pdf_text = page.get_text()
            should_vlm = (
                vlm_mode == "all"
                or (vlm_mode == "smart" and len(pdf_text.strip()) < text_threshold)
            )
            if should_vlm:
                try:
                    candidates = vlm.extract_questions(page_png)
                    error = None
                except Exception as exc:
                    candidates = []
                    error = str(exc)
            else:
                candidates = []
                error = None

            row = {
                "page": index,
                "page_image": f"images/{page_image.name}",
                "pdf_text": pdf_text,
                "content_images": content_images,
                "vlm_candidates": candidates,
                "vlm_skipped": not should_vlm,
                "error": error,
            }
            pages.append(row)
            with partial_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"{pdf_path.name} page {index}/{len(doc)} "
                f"vlm={should_vlm} candidates={len(candidates)} "
                f"images={len(content_images)} error={bool(error)}"
            )

    result = {
        "source_pdf": str(pdf_path),
        "pages": len(pages),
        "vlm_candidate_count": sum(len(p["vlm_candidates"]) for p in pages),
        "vlm_page_count": sum(1 for p in pages if not p.get("vlm_skipped")),
        "content_image_count": sum(len(p["content_images"]) for p in pages),
        "error_pages": [p["page"] for p in pages if p["error"]],
        "pages_detail": pages,
    }
    local_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if partial_jsonl.exists():
        partial_jsonl.unlink()
    return result


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
            current["stem"] = normalize(current["stem"])
            for option in current["options"]:
                option["text"] = normalize(option["text"])
            current["source_pages"] = sorted(current_pages)
            questions.append(current)
        current = None
        current_pages = set()

    for page_no in question_pages:
        for line in [x.strip() for x in normalize(page_texts[page_no]).splitlines() if x.strip()]:
            if is_chrome(line):
                continue
            if is_section(line):
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
    answer_text = normalize("\n".join(page_texts[p] for p in answer_pages))
    matches = list(ANSWER_RE.finditer(answer_text))
    answers: dict[int, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(answer_text)
        answers[number] = {
            "number": number,
            "correct_answer": answer_list(match.group(2)),
            "explanation": normalize(answer_text[start:end]),
            "source_pages": answer_pages,
        }
    return answers


def build_package(pdf_path: Path, local: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    page_texts = {p["page"]: p.get("pdf_text", "") for p in local["pages_detail"]}
    answer_start = next((p for p, text in page_texts.items() if ANSWER_MARKER in text), None)
    question_pages = list(range(1, answer_start)) if answer_start else list(page_texts)
    answer_pages = list(range(answer_start, len(page_texts) + 1)) if answer_start else []

    questions = parse_questions(page_texts, question_pages)
    answers = parse_answers(page_texts, answer_pages) if answer_pages else {}
    final_questions: list[dict[str, Any]] = []
    for question in questions:
        answer = answers.get(question["number"])
        expected_options = 0 if question["question_type"] == "判断" else 4
        issues: list[str] = []
        if len(question["options"]) != expected_options:
            issues.append(f"options {len(question['options'])}/{expected_options}")
        if answer_pages and not answer:
            issues.append("missing answer/explanation pair")
        final_questions.append(
            {
                **question,
                "correct_answer": answer["correct_answer"] if answer else [],
                "explanation": answer["explanation"] if answer else "",
                "answer_source_pages": answer["source_pages"] if answer else None,
                "needs_review": bool(issues),
                "review_reason": "; ".join(issues) if issues else None,
            }
        )

    lecture_blocks: list[dict[str, Any]] = []
    for page in local["pages_detail"]:
        page_no = page["page"]
        lines = [normalize(x) for x in page.get("pdf_text", "").splitlines()]
        text = "\n".join(line for line in lines if line and not is_chrome(line)).strip()
        lecture_blocks.append(
            {
                "page": page_no,
                "text": text,
                "images": page["content_images"],
                "page_image": page["page_image"],
                "vlm_candidates": page["vlm_candidates"],
                "error": page["error"],
            }
        )

    package = {
        "source_pdf": str(pdf_path),
        "summary": {
            "pages": local["pages"],
            "question_count": len(final_questions),
            "matched_answer_count": sum(bool(q["correct_answer"]) for q in final_questions),
            "review_count": sum(bool(q["needs_review"]) for q in final_questions),
            "lecture_block_count": len(lecture_blocks),
            "content_image_count": local["content_image_count"],
            "vlm_candidate_count": local["vlm_candidate_count"],
            "vlm_page_count": local.get("vlm_page_count", 0),
            "error_pages": local["error_pages"],
        },
        "questions": final_questions,
        "lecture_blocks": lecture_blocks,
        "answer_pages": answer_pages,
    }
    (out_dir / "complete-document-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(package, out_dir)
    return package


def write_markdown(package: dict[str, Any], out_dir: Path) -> None:
    md = ["# Complete Document Package", "", f"PDF: {Path(package['source_pdf']).name}", "", "## Summary"]
    for key, value in package["summary"].items():
        md.append(f"- {key}: {value}")
    md += ["", "## Lecture / Page Blocks"]
    for block in package["lecture_blocks"]:
        md.append(f"### Page {block['page']}")
        if block["text"]:
            md.append(block["text"][:2000])
        if block["images"]:
            md.append("Images: " + ", ".join(image["path"] for image in block["images"]))
        if block["vlm_candidates"]:
            md.append(f"VLM candidates: {len(block['vlm_candidates'])}")
        if block["error"]:
            md.append(f"Error: {block['error']}")
        md.append("")
    if package["questions"]:
        md += ["", "## Questions"]
        for question in package["questions"]:
            md.append(f"### Q{question['number']} {question['question_type']} {question['year']}")
            md.append(question["stem"])
            for option in question.get("options", []):
                md.append(f"- {option['key']}. {option['text']}")
            if question.get("correct_answer"):
                md.append("answer: " + "".join(question["correct_answer"]))
            if question.get("explanation"):
                md.append("explanation: " + question["explanation"][:500])
            if question.get("review_reason"):
                md.append("review: " + question["review_reason"])
            md.append("")
    (out_dir / "complete-document-package.md").write_text("\n".join(md), encoding="utf-8")


def process_one(pdf_path: Path, output_root: Path, *, vlm_mode: str) -> dict[str, Any]:
    out_dir = output_root / slug_name(pdf_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    local = collect_pages(pdf_path, out_dir, resume=True, vlm_mode=vlm_mode)
    package = build_package(pdf_path, local, out_dir)
    return {"pdf": str(pdf_path), "out_dir": str(out_dir), **package["summary"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="PDF file or directory containing PDFs")
    parser.add_argument("--out-dir", type=Path, default=Path.home() / "Downloads" / "needreadfile_output")
    parser.add_argument("--vlm-mode", choices=["smart", "all", "none"], default="smart")
    args = parser.parse_args(argv)

    input_path = args.input.resolve()
    pdfs = sorted(input_path.glob("*.pdf")) if input_path.is_dir() else [input_path]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summaries = [
        process_one(path.resolve(), args.out_dir.resolve(), vlm_mode=args.vlm_mode)
        for path in pdfs
    ]
    (args.out_dir / "_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out_dir.resolve())
    for row in summaries:
        print(
            f"{Path(row['pdf']).name}: pages={row['pages']} questions={row['question_count']} "
            f"answers={row['matched_answer_count']} images={row['content_image_count']} "
            f"vlm_pages={row.get('vlm_page_count', 0)} errors={row['error_pages']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
