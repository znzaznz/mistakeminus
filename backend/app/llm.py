"""文本大模型客户端：题目归类、相似题生成等。

真实 API 调用隔离在此层，单测里整体 mock。
"""

from __future__ import annotations

import json

from .config import settings

_CLASSIFY_PROMPT = """你是中级会计《经济法》题目分类助手。
把下面这道题归类到「{chapter}」的**唯一一个**知识点。

可选知识点（knowledge_point_name 必须与下列名称完全一致）：
{candidates}
{disambiguation}

题目：
{question}

只输出一个 JSON 对象，不要 markdown、不要额外说明：
{{"knowledge_point_name": "...", "confidence": 0.0~1.0}}
confidence 反映你对归类准确度的把握。"""

_CHAPTER_DISAMBIGUATION: dict[str, str] = {
    "总论": """
⚠️ 重要消歧规则（按考纲归类，别被"民事/民法"字样带偏）：
- **诉讼时效**（时效期间、中止、中断、起算、届满）→ 归「民事诉讼法律制度的规定」，**不是**「法律行为制度」。
- 管辖、上诉、再审、审判监督、两审终审、调解 → 「民事诉讼法律制度的规定」。
- 法律行为的成立/生效/无效/可撤销/效力待定、附条件附期限 → 「法律行为制度」。
- 代理（委托/法定/无权/表见/代理终止）→ 「代理制度」。
- 仲裁协议/范围/一裁终局/裁决 → 「仲裁法律制度的规定」。""",
}

_SIMILAR_PROMPT = """你是中级会计《经济法》命题助手。

任务：针对**下面这道原错题**，生成**一道新的**练习题。

硬性约束（违反任何一条都视为失败）：
1. **题型必须是「{question_type}」**，JSON 里 question_type 填「{question_type}」，不得改成其他题型。
   - 单选：4 个选项，correct_answer 仅 1 个字母
   - 多选：4 个选项，correct_answer 至少 2 个字母
   - 判断：options 为 [{{"key":"对","text":"对"}}, {{"key":"错","text":"错"}}]，correct_answer 为 ["对"] 或 ["错"]
2. **考点锁定为「{knowledge_point_name}」**，只考这个知识点，禁止换成同章其他知识点。
3. **必须紧扣本道原错题的考查意图**（看原题问的是什么、考的是哪条规则/哪种情形），在此基础上换案情、换选项、换问法。
   - 禁止照抄原题
   - 禁止出一道「只是同知识点、但与原题考查角度无关」的题（例如原题考「基本原则」，不要换成「哪些纠纷可仲裁」）
4. stem 只放题干；选项放 options；必须自带 explanation。

知识点要义（命题边界，勿超出）：
{essence}

原错题（你的出题锚点，必须在此基础上变形）：
{original}

只输出一个 JSON 对象，不要 markdown：
{{"stem": "...", "question_type": "{question_type}", "options": [{{"key":"A","text":"..."}}], "correct_answer": ["A"], "explanation": "..."}}"""


class LLMError(RuntimeError):
    pass


def _build_client():
    from openai import OpenAI

    if not settings.dashscope_api_key.strip():
        raise LLMError("未配置 DASHSCOPE_API_KEY，无法调用文本模型")
    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


def _parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data, _ = json.JSONDecoder().raw_decode(text)
    if not isinstance(data, dict):
        raise LLMError(f"期望 JSON 对象，得到 {type(data)}")
    return data


def classify_question(
    question_text: str,
    candidates: list[dict],
    *,
    chapter: str = "总论",
    client=None,
) -> dict:
    """调用文本模型归类一题。返回 {knowledge_point_name, confidence}。"""
    client = client or _build_client()
    lines = []
    for c in candidates:
        hint = (c.get("essence") or "")[:120].replace("\n", " ")
        lines.append(f"- {c['name']}" + (f"（{hint}…）" if hint else ""))
    prompt = _CLASSIFY_PROMPT.format(
        chapter=chapter,
        candidates="\n".join(lines),
        disambiguation=_CHAPTER_DISAMBIGUATION.get(chapter, ""),
        question=question_text,
    )
    resp = client.chat.completions.create(
        model=settings.qwen_text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    content = resp.choices[0].message.content or ""
    data = _parse_json_object(content)
    return {
        "knowledge_point_name": str(data.get("knowledge_point_name", "")).strip(),
        "confidence": float(data.get("confidence", 0)),
    }


def generate_similar_question(
    essence: str,
    original_text: str,
    question_type: str,
    knowledge_point_name: str,
    *,
    client=None,
) -> dict:
    """生成一道相似题原始 dict（未校验）。"""
    client = client or _build_client()
    prompt = _SIMILAR_PROMPT.format(
        essence=essence or "（要义暂无）",
        original=original_text,
        question_type=question_type,
        knowledge_point_name=knowledge_point_name,
    )
    resp = client.chat.completions.create(
        model=settings.qwen_text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
    )
    content = resp.choices[0].message.content or ""
    data = _parse_json_object(content)
    data["question_type"] = question_type
    return data
