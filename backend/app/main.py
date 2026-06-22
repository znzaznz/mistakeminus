"""FastAPI 应用入口。

S0：端到端健康检查。
S2：取题 / 作答接口。
"""

import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db, grading, mistakes, repository
from .classify import format_question_text
from .config import settings
from .llm import LLMError, generate_similar_question
from .similar import (
    delete_saved_similar_for_origin,
    delete_similar_question,
    draft_from_llm,
    get_saved_similar_question_id,
    insert_similar_question,
    normalize_similar_draft,
)
from .weakness import rank_weaknesses
from .sm2 import quality_from_correct, sm2_schedule
from .uploads import (
    confirm_upload,
    draft_from_confirm_body,
    get_draft,
    insert_draft,
    save_upload_image,
)
from .extraction import vlm
from .schemas import (
    AttemptRequest,
    AttemptResult,
    ConfirmUploadRequest,
    DailyTaskSummary,
    DailyTaskQuestion,
    MistakeItem,
    QuestionPublic,
    SimilarQuestionOut,
    QuestionReviewItem,
    SettingsOut,
    SettingsUpdate,
    SetKnowledgePointRequest,
    UploadDraftOut,
    WeaknessItem,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保数据库文件存在、基础 schema 就绪
    db.init_db()
    # 全新库（或删库重来）：从 data/imports/*.jsonl 重建题库数据，已有数据则跳过
    conn = db.get_connection()
    try:
        db.seed_from_snapshot(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="MistakeGenie API", version="0.0.1", lifespan=lifespan)

# 本地单用户，前端跑在 Vite dev server（默认 5173），允许其跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 题目配图等本地媒体文件
settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")


def get_db() -> Iterator[sqlite3.Connection]:
    """每个请求一个连接。测试可通过 dependency_overrides 注入临时库。"""
    conn = db.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict:
    """端到端健康检查：服务在线、SQLite 可连、关键配置是否就绪。

    只报告配置项是否已填，绝不返回 key 值本身。
    """
    db_ok = db.check_connection()
    config = settings.config_presence()
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "database": "ok" if db_ok else "error",
        "config": config,
    }


@app.get("/questions", response_model=list[QuestionPublic])
def list_questions(
    limit: int = Query(default=10, ge=1, le=100),
    knowledge_point_id: int | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """取一批题供练习（不含正确答案/解析）。可按知识点筛选。"""
    return repository.get_practice_questions(
        conn, limit=limit, knowledge_point_id=knowledge_point_id
    )


@app.get("/questions/review", response_model=list[QuestionReviewItem])
def list_review_questions(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """待人工确认队列（识别/归类低置信）。"""
    return repository.list_review_questions(conn)


@app.patch("/questions/{question_id}")
def patch_question(
    question_id: int,
    req: SetKnowledgePointRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """人工改挂知识点；可选清除待确认标记。"""
    try:
        repository.set_question_knowledge_point(
            conn,
            question_id,
            req.knowledge_point_id,
            clear_review=req.clear_review,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="题目或知识点不存在")
    return {"ok": True, "question_id": question_id, "knowledge_point_id": req.knowledge_point_id}


@app.get("/questions/{question_id}/similar", response_model=SimilarQuestionOut)
def get_saved_similar_question(
    question_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """返回该错题已保存的相似题；无则 404。"""
    saved_id = get_saved_similar_question_id(conn, question_id)
    if saved_id is None:
        raise HTTPException(status_code=404, detail="尚无已保存的相似题")
    public = repository.get_question_public(conn, saved_id)
    if public is None:
        raise HTTPException(status_code=404, detail="尚无已保存的相似题")
    return {**public, "cached": True, "origin_question_id": question_id}


def _generate_and_save_similar(conn, question_id: int, row, kp) -> dict:
    original_text = format_question_text(row["stem"], row["options"])
    try:
        raw = generate_similar_question(
            kp["essence"] or "",
            original_text,
            row["question_type"],
            kp["name"],
        )
        draft = normalize_similar_draft(
            draft_from_llm(raw), question_type=row["question_type"]
        )
    except (LLMError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e))

    new_id = insert_similar_question(
        conn,
        draft,
        knowledge_point_id=row["knowledge_point_id"],
        origin_question_id=question_id,
        chapter=row["chapter"],
        exam_point=row["exam_point"],
    )
    public = repository.get_question_public(conn, new_id)
    if public is None:
        raise HTTPException(status_code=500, detail="相似题入库失败")
    return {**public, "cached": False, "origin_question_id": question_id}


@app.post("/questions/{question_id}/similar", response_model=SimilarQuestionOut)
def create_similar_question(
    question_id: int,
    regenerate: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """基于原错题 + 知识点生成相似题。每道原错题独立绑定；regenerate=true 重新生成。"""
    if not regenerate:
        saved_id = get_saved_similar_question_id(conn, question_id)
        if saved_id is not None:
            public = repository.get_question_public(conn, saved_id)
            if public is not None:
                return {**public, "cached": True, "origin_question_id": question_id}

    row = repository.get_question(conn, question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if row["knowledge_point_id"] is None:
        raise HTTPException(status_code=400, detail="原题未归类到知识点，无法生成相似题")
    kp = repository.get_knowledge_point(conn, row["knowledge_point_id"])
    if kp is None:
        raise HTTPException(status_code=400, detail="知识点不存在")

    if regenerate:
        delete_saved_similar_for_origin(conn, question_id)

    return _generate_and_save_similar(conn, question_id, row, kp)


@app.delete("/questions/{question_id}")
def remove_similar_question(
    question_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """报错删除：仅允许删除 AI 生成的相似题。"""
    if not delete_similar_question(conn, question_id):
        raise HTTPException(status_code=404, detail="题目不存在或不可删除")
    return {"ok": True, "question_id": question_id}


@app.get("/weaknesses", response_model=list[WeaknessItem])
def list_weaknesses(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """薄弱知识点列表，按复习优先级降序。"""
    stats = repository.fetch_kp_attempt_stats(conn)
    items = rank_weaknesses(stats)
    return [
        {
            "knowledge_point_id": i.knowledge_point_id,
            "name": i.name,
            "chapter": i.chapter,
            "mastery_requirement": i.mastery_requirement,
            "attempt_count": i.attempt_count,
            "correct_count": i.correct_count,
            "wrong_count": i.wrong_count,
            "mistake_count": i.mistake_count,
            "accuracy": i.accuracy,
            "last_attempt_at": i.last_attempt_at,
            "priority": i.priority,
            "tags": list(i.tags),
        }
        for i in items
    ]


@app.post("/attempts", response_model=AttemptResult)
def submit_attempt(
    req: AttemptRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> AttemptResult:
    """提交一道题的作答：判对错、落库，返回正确答案与解析。"""
    import json

    row = repository.get_question(conn, req.question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    correct_answer = json.loads(row["correct_answer"])
    is_correct = grading.judge(correct_answer, req.user_answer)
    repository.record_attempt(conn, req.question_id, req.user_answer, is_correct)

    # SM-2 复习状态更新（S9）
    today = date.today()
    sm2_state = repository.get_sm2_state(conn, req.question_id)
    quality = quality_from_correct(is_correct)
    new_sm2 = sm2_schedule(sm2_state, quality, today)
    repository.upsert_sm2_state(conn, req.question_id, new_sm2)

    # 今日任务进度（S9）
    task_date = today.isoformat()
    repository.mark_daily_item_complete(conn, task_date, req.question_id)

    # 更新错题本：答错自动收录 / 重复出错累加 / 已收录题答对累加
    now = datetime.now().isoformat(timespec="seconds")
    current = repository.get_mistake(conn, req.question_id)
    updated = mistakes.apply_attempt(
        current,
        is_correct=is_correct,
        user_answer=req.user_answer,
        correct_answer=correct_answer,
        now=now,
    )
    if updated is not None:
        repository.upsert_mistake(conn, req.question_id, updated)

    return AttemptResult(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=row["explanation"],
    )


@app.get("/mistakes", response_model=list[MistakeItem])
def list_mistakes(
    favorite_only: bool = Query(default=False),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """错题本：列出错题及追踪字段，按最近作答倒序。"""
    return repository.list_mistakes(conn, favorite_only=favorite_only)


@app.post("/mistakes/{question_id}/favorite")
def toggle_favorite(
    question_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """切换错题收藏状态。"""
    try:
        favorite = repository.toggle_mistake_favorite(conn, question_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="错题不存在")
    return {"question_id": question_id, "favorite": favorite}


@app.get("/taxonomy")
def get_taxonomy(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    """知识点体系：章 → 考点 → 知识点（含能力要求、要义、挂题数）。"""
    return repository.get_taxonomy(conn)


@app.get("/settings", response_model=SettingsOut)
def get_settings(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return {
        "daily_target_count": int(
            repository.get_setting(conn, "daily_target_count", "30")
        ),
    }


@app.put("/settings", response_model=SettingsOut)
def update_settings(
    req: SettingsUpdate,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    repository.set_setting(conn, "daily_target_count", str(req.daily_target_count))
    return {"daily_target_count": req.daily_target_count}


@app.get("/daily-task", response_model=DailyTaskSummary)
def get_daily_task(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    task_date = date.today().isoformat()
    return repository.get_daily_task_summary(conn, task_date)


@app.get("/daily-task/questions", response_model=list[DailyTaskQuestion])
def get_daily_task_questions(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    task_date = date.today().isoformat()
    return repository.get_daily_task_questions(conn, task_date)


@app.post("/uploads", response_model=UploadDraftOut)
async def upload_screenshot(
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """上传错题截图，VLM 识题返回可编辑草稿。"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    suffix = Path(file.filename or "").suffix or ".png"
    image_path = save_upload_image(data, settings.media_dir, suffix=suffix)
    try:
        raw_list = vlm.extract_questions(data)
    except vlm.VLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not raw_list:
        raise HTTPException(status_code=422, detail="未识别到题目")
    raw = raw_list[0]
    draft_id = insert_draft(conn, image_path, raw)
    draft = get_draft(conn, draft_id)
    return draft


@app.get("/uploads/{draft_id}", response_model=UploadDraftOut)
def get_upload_draft(
    draft_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    draft = get_draft(conn, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return draft


@app.post("/uploads/{draft_id}/confirm")
def confirm_upload_draft(
    draft_id: int,
    req: ConfirmUploadRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    stored = get_draft(conn, draft_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="草稿不存在")
    body = {
        "stem": req.stem,
        "question_type": req.question_type,
        "options": [o.model_dump() for o in req.options],
        "correct_answer": req.correct_answer,
        "explanation": req.explanation or "",
        "confidence": stored.get("confidence", 1.0),
        "chapter": req.chapter,
        "exam_point": req.exam_point,
    }
    try:
        draft = draft_from_confirm_body(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    now = datetime.now().isoformat(timespec="seconds")
    qid = confirm_upload(
        conn,
        draft_id,
        draft,
        knowledge_point_id=req.knowledge_point_id,
        image_path=stored["image_path"],
        now=now,
    )
    return {"ok": True, "question_id": qid}


@app.get("/knowledge-points")
def list_knowledge_points(conn: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    return repository.list_knowledge_points_brief(conn)
