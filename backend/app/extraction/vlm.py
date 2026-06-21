"""视觉大模型客户端：整页图 → 该页题目的结构化 JSON。

这一层把真实 API 调用隔离起来，单测里整体 mock 掉（不打真实 API）。
"""

from __future__ import annotations

import base64
import json

import httpx

from ..config import settings

# 给 VLM 的指令：逐页识题，返回严格 JSON。
_SYSTEM_PROMPT = """你是一个会计考试题目识别助手。我会给你一页讲义/真题的整页截图。
请识别这一页上的所有题目，按从上到下顺序，输出**严格 JSON**，形如：
{"questions": [
  {
    "stem": "题干文本",
    "question_type": "单选" | "多选" | "判断",
    "options": [{"key": "A", "text": "选项内容"}, ...],
    "correct_answer": ["A"],
    "explanation": "解析文本，没有就留空字符串",
    "chapter": "所属章节，如 第一章 总论",
    "exam_point": "所属考点",
    "year": "年份，如 2023，识别不出就 null",
    "has_image": true/false,
    "confidence": 0.0~1.0
  }
]}
要求：
- 只输出**一个** JSON 对象，不要任何额外说明、不要 markdown 代码块、JSON 之后不要再输出任何文字。
- **stem 只放题干本身，绝对不要把 A/B/C/D 选项文字写进 stem**；选项一律只放在 options 数组里。
- 题干里若带题号（如「5.」「17.【单选·2024】」）可保留，但选项必须从题干剥离。
- year 用字符串，如 "2024"；识别不出用 null。
- 若该页没有完整题目（如纯讲义/目录页），返回 {"questions": []}。
- 解析（explanation）只在本页确实出现时填写，没有就留空字符串，不要编造。
- has_image 表示该题是否配有图示/表格。
- confidence 反映你对识别准确度的把握，模糊不清的题给低分。"""


class VLMError(RuntimeError):
    pass


def _build_client():
    # 延迟导入，避免无 key 环境下 import 即失败
    from openai import OpenAI

    if not settings.dashscope_api_key.strip():
        raise VLMError("未配置 DASHSCOPE_API_KEY，无法调用视觉模型")
    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def _extract_questions_ollama(page_png: bytes) -> list[dict]:
    b64 = base64.b64encode(page_png).decode("ascii")
    prompt = _SYSTEM_PROMPT + "\n\n识别这一页上的所有题目。只输出 JSON。"
    url = settings.ollama_base_url.rstrip("/") + "/api/generate"
    try:
        with httpx.Client(trust_env=False, timeout=180) as http:
            resp = http.post(
                url,
                json={
                    "model": settings.ollama_vl_model,
                    "prompt": prompt,
                    "images": [b64],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
            )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise VLMError(f"Ollama 调用失败: {e}") from e

    data = resp.json()
    content = data.get("response") or data.get("thinking") or ""
    if not content:
        raise VLMError("Ollama 返回为空")
    return _parse_questions_json(content)


def _parse_questions_json(content: str) -> list[dict]:
    text = content.strip()
    # 容忍模型偶尔包了 ```json ``` 代码块
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    # 容忍 JSON 后面跟了多余文字（"Extra data"）：只取第一个完整 JSON 值
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data, _ = json.JSONDecoder().raw_decode(text)
    questions = data.get("questions", data if isinstance(data, list) else [])
    if not isinstance(questions, list):
        raise VLMError(f"VLM 返回的 questions 不是列表: {type(questions)}")
    return questions


def extract_questions(page_png: bytes, client=None) -> list[dict]:
    """对一页整页图调用 VLM，返回该页题目的原始 dict 列表（未校验）。"""
    if settings.vlm_provider.lower() == "ollama":
        return _extract_questions_ollama(page_png)

    client = client or _build_client()
    b64 = base64.b64encode(page_png).decode("ascii")
    resp = client.chat.completions.create(
        model=settings.qwen_vl_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "识别这一页上的所有题目。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            },
        ],
        temperature=0.1,
    )
    content = resp.choices[0].message.content or ""
    return _parse_questions_json(content)
