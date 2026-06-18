import { useEffect, useState } from "react";
import { fetchWeaknesses } from "./api";
import type { Weakness } from "./types";

export default function WeaknessPage() {
  const [items, setItems] = useState<Weakness[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWeaknesses().then(setItems).catch((e) => setError(String(e)));
  }, []);

  if (error)
    return <div className="page"><p className="error-text">{error}</p></div>;
  if (!items)
    return <div className="page"><p className="loading-text">分析薄弱点中…</p></div>;
  if (items.length === 0)
    return (
      <div className="page">
        <h2 className="page-title">薄弱点分析</h2>
        <div className="card card--flat" style={{ textAlign: "center", padding: "40px 24px" }}>
          <div className="state-icon">📊</div>
          <p className="state-desc" style={{ margin: 0 }}>
            还没有作答数据 —— 先去刷几道题，再来这里看薄弱知识点。
          </p>
        </div>
      </div>
    );

  return (
    <div className="page">
      <h2 className="page-title">薄弱点分析</h2>
      <p className="page-desc">按复习优先级排序，分数越高越建议先补</p>
      {items.map((w, i) => (
        <article key={w.knowledge_point_id} className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
            <div>
              <div className="mistake-card__meta">
                #{i + 1} · {w.chapter}
                {w.mastery_requirement ? ` · ${w.mastery_requirement}` : ""}
              </div>
              <h3 className="weakness-card__title">{w.name}</h3>
            </div>
            <span className="badge badge--score">优先级 {w.priority}</span>
          </div>
          <div className="mistake-card__stats" style={{ marginBottom: 10 }}>
            <span>做题 {w.attempt_count} 次</span>
            <span>正确率 {w.accuracy != null ? `${Math.round(w.accuracy * 100)}%` : "—"}</span>
            <span>错题 {w.mistake_count} 道</span>
            <span>错 {w.wrong_count} 次</span>
          </div>
          {w.tags.length > 0 && (
            <div className="tag-list">
              {w.tags.map((t) => (
                <span key={t} className="tag">{t}</span>
              ))}
            </div>
          )}
          {w.last_attempt_at && (
            <div className="timestamp">
              最近作答 {w.last_attempt_at.replace("T", " ")}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
