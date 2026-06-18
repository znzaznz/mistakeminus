import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchMistakes, toggleMistakeFavorite, mediaUrl } from "./api";
import SimilarDrill from "./SimilarDrill";
import type { Mistake } from "./types";

/** 错题本题干：把挤在一行的 A/B/C/D 拆成逐行显示（仅本页用） */
function formatMistakeStem(stem: string): string {
  return stem.replace(/\r\n/g, "\n").replace(/(\s)([A-D][.、．]\s)/g, "\n$2");
}

function useMistakePageSize(): number {
  const [size, setSize] = useState(() => (window.innerWidth >= 768 ? 5 : 1));
  useEffect(() => {
    const onResize = () => setSize(window.innerWidth >= 768 ? 5 : 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return size;
}

export default function MistakeBook() {
  const pageSize = useMistakePageSize();
  const [mistakes, setMistakes] = useState<Mistake[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const [drillOpen, setDrillOpen] = useState(false);
  const [drillLoading, setDrillLoading] = useState(false);

  const load = useCallback(() => {
    setError(null);
    fetchMistakes(favoriteOnly)
      .then((list) => {
        setMistakes(list);
        setActiveIdx(0);
        setDrillOpen(false);
      })
      .catch((e) => setError(String(e)));
  }, [favoriteOnly]);

  useEffect(() => {
    if (mistakes === null) load();
  }, [load, mistakes]);

  useEffect(() => {
    if (!mistakes?.length) return;
    setActiveIdx((i) => Math.min(i, mistakes.length - 1));
  }, [pageSize, mistakes?.length]);

  const total = mistakes?.length ?? 0;
  const pageStart = Math.floor(activeIdx / pageSize) * pageSize;
  const visible = useMemo(
    () => (mistakes ? mistakes.slice(pageStart, pageStart + pageSize) : []),
    [mistakes, pageStart, pageSize]
  );
  const current = mistakes?.[activeIdx] ?? null;

  async function onToggleFavorite(questionId: number) {
    try {
      const fav = await toggleMistakeFavorite(questionId);
      setMistakes((prev) =>
        prev
          ?.map((m) => (m.question_id === questionId ? { ...m, favorite: fav } : m))
          .filter((m) => !favoriteOnly || m.favorite) ?? null
      );
    } catch (e) {
      setError(String(e));
    }
  }

  function goPrev() {
    setDrillOpen(false);
    setDrillLoading(false);
    setActiveIdx((i) => Math.max(0, i - 1));
  }

  function goNext() {
    setDrillOpen(false);
    setDrillLoading(false);
    setActiveIdx((i) => Math.min(total - 1, i + 1));
  }

  function onDrillAdvance() {
    setDrillOpen(false);
    setDrillLoading(false);
    if (activeIdx < total - 1) {
      setActiveIdx((i) => i + 1);
    }
  }

  if (error)
    return (
      <div className="page">
        <p className="error-text">{error}</p>
      </div>
    );
  if (!mistakes)
    return (
      <div className="page">
        <p className="loading-text">加载错题本中…</p>
      </div>
    );

  return (
    <div className="mistake-book">
      <div className="mistake-book__scroll page">
        <h2 className="page-title">错题本</h2>
        <div className="toolbar">
          <p className="page__meta" style={{ margin: 0 }}>
            共 {total} 道{favoriteOnly ? "收藏" : "错题"}
            {total > 0 && ` · 当前 ${activeIdx + 1}/${total}`}
          </p>
          <button
            className={`btn btn--sm${favoriteOnly ? " btn--primary" : " btn--secondary"}`}
            onClick={() => {
              setMistakes(null);
              setFavoriteOnly((v) => !v);
            }}
          >
            {favoriteOnly ? "显示全部" : "只看收藏"}
          </button>
        </div>

        {total === 0 ? (
          <div className="card card--flat" style={{ textAlign: "center", padding: "40px 24px" }}>
            <div className="state-icon">📝</div>
            <p className="state-desc" style={{ margin: 0 }}>
              {favoriteOnly
                ? "还没有收藏的错题。"
                : "错题本还是空的 —— 去刷题，答错的题会自动收进来。"}
            </p>
          </div>
        ) : (
          visible.map((m, i) => {
            const idx = pageStart + i;
            const isActive = idx === activeIdx;
            return (
              <article
                key={m.question_id}
                className={`card mistake-card${isActive ? " mistake-card--active" : ""}`}
                onClick={() => {
                  setDrillOpen(false);
                  setActiveIdx(idx);
                }}
              >
                <div className="mistake-card__header">
                  <div className="mistake-card__meta">
                    {m.question_type}
                    {m.knowledge_point_name
                      ? ` · ${m.knowledge_point_name}`
                      : m.exam_point
                        ? ` · ${m.exam_point}`
                        : ""}
                    {m.year ? ` · ${m.year}` : ""}
                  </div>
                  <button
                    className="fav-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleFavorite(m.question_id);
                    }}
                    title={m.favorite ? "取消收藏" : "收藏"}
                  >
                    {m.favorite ? "★" : "☆"}
                  </button>
                </div>
                <div className="mistake-card__stem">{formatMistakeStem(m.stem)}</div>
                {m.images && m.images.length > 0 && (
                  <img
                    src={mediaUrl(m.images[0])}
                    alt="错题原图"
                    className="question-card__img"
                  />
                )}
                <div className="mistake-card__stats">
                  <span className="stat--wrong">你的答案：{m.wrong_answer.join("、") || "—"}</span>
                  <span className="stat--right">正确答案：{m.correct_answer.join("、")}</span>
                  <span>
                    错 {m.wrong_count} 次 · 对 {m.correct_count} 次
                  </span>
                  <span className="mastery-tag">{m.mastery}</span>
                </div>
                <div className="timestamp">最近作答 {m.last_attempt_at.replace("T", " ")}</div>
              </article>
            );
          })
        )}

        {total > pageSize && (
          <div className="mistake-book__pager">
            <button
              className="btn btn--secondary btn--sm"
              disabled={pageStart === 0}
              onClick={() => {
                setDrillOpen(false);
                setActiveIdx(Math.max(0, pageStart - pageSize));
              }}
            >
              上一页
            </button>
            <span className="mistake-book__pager-label">
              {pageStart + 1}–{Math.min(pageStart + pageSize, total)} / {total}
            </span>
            <button
              className="btn btn--secondary btn--sm"
              disabled={pageStart + pageSize >= total}
              onClick={() => {
                setDrillOpen(false);
                setActiveIdx(Math.min(total - 1, pageStart + pageSize));
              }}
            >
              下一页
            </button>
          </div>
        )}
      </div>

      {total > 0 && current && (
        <div className="mistake-book__dock">
          {drillOpen && (
            <SimilarDrill
              originQuestionId={current.question_id}
              autoStart
              onAdvance={onDrillAdvance}
              onClose={() => {
                setDrillOpen(false);
                setDrillLoading(false);
              }}
              onLoadingChange={setDrillLoading}
            />
          )}
          <div className="mistake-book__dock-bar">
            <button
              className="btn btn--secondary btn--sm"
              disabled={activeIdx === 0 || drillLoading}
              onClick={goPrev}
            >
              上一道
            </button>
            <button
              className={`btn btn--primary mistake-book__drill-btn${drillLoading ? " btn--loading" : ""}`}
              disabled={drillLoading}
              onClick={() => setDrillOpen(true)}
            >
              {drillLoading ? "加载中…" : "再练一道同知识点"}
            </button>
            <button
              className="btn btn--secondary btn--sm"
              disabled={activeIdx >= total - 1 || drillLoading}
              onClick={goNext}
            >
              下一道
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
