import { useEffect, useMemo, useState } from "react";
import {
  fetchDailyTask,
  fetchDailyTaskQuestions,
  mediaUrl,
  submitAttempt,
} from "./api";
import type { AttemptResult, DailyTaskSummary, Option, DailyTaskQuestion } from "./types";

function effectiveOptions(q: DailyTaskQuestion): Option[] {
  if (q.options.length > 0) return q.options;
  if (q.question_type === "判断") {
    return [
      { key: "对", text: "对" },
      { key: "错", text: "错" },
    ];
  }
  return [];
}

function optionClass(chosen: boolean, result: AttemptResult | null, isAnswer: boolean): string {
  let cls = "option-btn";
  if (result) {
    if (isAnswer) cls += " option-btn--correct";
    else if (chosen) cls += " option-btn--wrong";
  } else if (chosen) {
    cls += " option-btn--selected";
  }
  return cls;
}

export default function Practice() {
  const [summary, setSummary] = useState<DailyTaskSummary | null>(null);
  const [questions, setQuestions] = useState<DailyTaskQuestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setQuestions(null);
    setError(null);
    setIdx(0);
    setSelected([]);
    setResult(null);
    setCorrectCount(0);
    try {
      const [s, qs] = await Promise.all([
        fetchDailyTask(),
        fetchDailyTaskQuestions(),
      ]);
      setSummary(s);
      const pending = qs.filter((q) => !q.completed);
      setQuestions(pending.length > 0 ? pending : qs);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const q = questions?.[idx];
  const options = useMemo(() => (q ? effectiveOptions(q) : []), [q]);
  const isMulti = q?.question_type === "多选";
  const progressPct = summary && summary.total > 0 ? (summary.completed / summary.total) * 100 : 0;

  function toggle(key: string) {
    if (result) return;
    if (isMulti) {
      setSelected((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));
    } else {
      setSelected([key]);
    }
  }

  async function onSubmit() {
    if (!q || selected.length === 0) return;
    setSubmitting(true);
    try {
      const res = await submitAttempt(q.id, selected);
      setResult(res);
      if (res.is_correct) setCorrectCount((c) => c + 1);
      const s = await fetchDailyTask();
      setSummary(s);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function onNext() {
    setSelected([]);
    setResult(null);
    setIdx((i) => i + 1);
  }

  if (error)
    return (
      <Centered>
        <p className="error-text">{error}</p>
        <button className="btn btn--primary" onClick={load}>重试</button>
      </Centered>
    );
  if (!questions || !summary)
    return <Centered><p className="loading-text">加载今日任务中…</p></Centered>;

  if (summary.completed >= summary.total && summary.total > 0) {
    return (
      <Centered>
        <div className="state-icon">🎉</div>
        <h2 className="state-title">今日任务完成</h2>
        <p className="state-desc">共 {summary.total} 题已全部做完，明天再来！</p>
        <button className="btn btn--primary" onClick={load}>刷新</button>
      </Centered>
    );
  }

  if (questions.length === 0)
    return <Centered><p className="state-desc">今日暂无题目，请先导入题库。</p></Centered>;

  if (idx >= questions.length) {
    return (
      <Centered>
        <div className="state-icon">✅</div>
        <h2 className="state-title">本批完成</h2>
        <p className="state-desc">
          进度 {summary.completed}/{summary.total} · 本批答对 {correctCount} 题
        </p>
        <button className="btn btn--primary" onClick={load}>继续今日任务</button>
      </Centered>
    );
  }

  return (
    <div className="page">
      <div className="progress-bar">
        <div className="progress-bar__fill" style={{ width: `${progressPct}%` }} />
      </div>

      <div className="question-card">
        <div className="question-card__meta">
          <span className="badge">今日 {summary.completed}/{summary.total}</span>
          <span className="badge badge--muted">{q!.question_type}</span>
        </div>

        <h3 className="question-card__stem">{q!.stem}</h3>

        {q!.images.map((src) => (
          <img key={src} src={mediaUrl(src)} alt="题目配图" className="question-card__img" />
        ))}

        <ul className="option-list">
          {options.map((o) => {
            const chosen = selected.includes(o.key);
            const isAnswer = !!result?.correct_answer.includes(o.key);
            return (
              <li key={o.key}>
                <button
                  className={optionClass(chosen, result, isAnswer)}
                  onClick={() => toggle(o.key)}
                  disabled={!!result}
                >
                  <strong>{o.key}.</strong> {o.text}
                </button>
              </li>
            );
          })}
        </ul>

        {!result ? (
          <button
            className="btn btn--primary"
            onClick={onSubmit}
            disabled={selected.length === 0 || submitting}
          >
            {submitting ? "提交中…" : isMulti ? "提交答案（多选）" : "提交答案"}
          </button>
        ) : (
          <div className={`result-panel${result.is_correct ? " result-panel--correct" : " result-panel--wrong"}`}>
            <p className={`result-panel__title${result.is_correct ? " result-panel__title--correct" : " result-panel__title--wrong"}`}>
              {result.is_correct ? "回答正确" : "回答错误"}
            </p>
            <p>正确答案：{result.correct_answer.join("、")}</p>
            {result.explanation && <p>解析：{result.explanation}</p>}
            <button className="btn btn--primary" onClick={onNext} style={{ marginTop: 12 }}>
              下一题 →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="page page--centered">{children}</div>;
}
