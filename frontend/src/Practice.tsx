import { useEffect, useMemo, useState } from "react";
import {
  fetchDailyTask,
  fetchDailyTaskQuestions,
  fetchQuestions,
  mediaUrl,
  submitAttempt,
} from "./api";
import type { AttemptResult, DailyTaskSummary, Option, Question } from "./types";

const SUBJECT_BATCH = 20; // 按科目刷题：每组题量

function effectiveOptions(q: Question): Option[] {
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

export default function Practice({ subject = "" }: { subject?: string }) {
  const subjectMode = subject !== "";
  const [summary, setSummary] = useState<DailyTaskSummary | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
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
      if (subjectMode) {
        // 按科目刷题：直接从该科目题池随机取一组，不走每日任务/SM2
        setSummary(null);
        setQuestions(await fetchQuestions(SUBJECT_BATCH, subject));
      } else {
        const [s, qs] = await Promise.all([
          fetchDailyTask(),
          fetchDailyTaskQuestions(),
        ]);
        setSummary(s);
        const pending = qs.filter((q) => !q.completed);
        setQuestions(pending.length > 0 ? pending : qs);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subject]);

  const q = questions?.[idx];
  const options = useMemo(() => (q ? effectiveOptions(q) : []), [q]);
  const isMulti = q?.question_type === "多选";
  // 进度：每日任务用后端 summary；按科目用本组本地进度（已答 idx / 本组题量）
  const total = subjectMode ? questions?.length ?? 0 : summary?.total ?? 0;
  const completed = subjectMode ? idx : summary?.completed ?? 0;
  const progressPct = total > 0 ? (completed / total) * 100 : 0;

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
      if (!subjectMode) {
        const s = await fetchDailyTask();
        setSummary(s);
      }
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
  if (!questions || (!subjectMode && !summary))
    return (
      <Centered>
        <p className="loading-text">{subjectMode ? "加载题目中…" : "加载今日任务中…"}</p>
      </Centered>
    );

  if (!subjectMode && summary && summary.completed >= summary.total && summary.total > 0) {
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
    return (
      <Centered>
        <p className="state-desc">
          {subjectMode ? `「${subject}」暂无可刷题目。` : "今日暂无题目，请先导入题库。"}
        </p>
      </Centered>
    );

  if (idx >= questions.length) {
    return (
      <Centered>
        <div className="state-icon">✅</div>
        <h2 className="state-title">本组完成</h2>
        <p className="state-desc">
          {subjectMode
            ? `「${subject}」本组 ${questions.length} 题 · 答对 ${correctCount} 题`
            : `进度 ${summary!.completed}/${summary!.total} · 本批答对 ${correctCount} 题`}
        </p>
        <button className="btn btn--primary" onClick={load}>
          {subjectMode ? "再来一组" : "继续今日任务"}
        </button>
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
          <span className="badge">
            {subjectMode ? `${subject} ${completed}/${total}` : `今日 ${completed}/${total}`}
          </span>
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
