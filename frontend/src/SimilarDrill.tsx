import { useEffect, useMemo, useState } from "react";
import { deleteQuestion, generateSimilar, submitAttempt } from "./api";
import type { AttemptResult, Option, Question } from "./types";

type Props = {
  originQuestionId: number;
  onClose: () => void;
  autoStart?: boolean;
  onAdvance?: () => void;
  onLoadingChange?: (loading: boolean) => void;
};

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

export default function SimilarDrill({
  originQuestionId,
  onClose,
  autoStart = false,
  onAdvance,
  onLoadingChange,
}: Props) {
  const [question, setQuestion] = useState<Question | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const options = useMemo(() => (question ? effectiveOptions(question) : []), [question]);
  const isMulti = question?.question_type === "多选";

  function setBusy(busy: boolean) {
    setLoading(busy);
    onLoadingChange?.(busy);
  }

  async function loadOrGenerate(regenerate = false) {
    setBusy(true);
    setError(null);
    setResult(null);
    setSelected([]);
    if (regenerate) setQuestion(null);
    try {
      const q = await generateSimilar(originQuestionId, regenerate);
      if (q.origin_question_id != null && q.origin_question_id !== originQuestionId) {
        throw new Error("返回的相似题与当前错题不匹配，请重试");
      }
      setQuestion(q);
      setFromCache(!!q.cached);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!autoStart) return;
    loadOrGenerate(false);
  }, [originQuestionId, autoStart]);

  function toggle(key: string) {
    if (result) return;
    if (isMulti) {
      setSelected((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));
    } else {
      setSelected([key]);
    }
  }

  async function onSubmit() {
    if (!question || selected.length === 0) return;
    setSubmitting(true);
    try {
      const res = await submitAttempt(question.id, selected);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function onReportDelete() {
    if (!question) return;
    try {
      await deleteQuestion(question.id);
      setQuestion(null);
      setFromCache(false);
      onClose();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="similar-drill">
      {loading && !question && (
        <p className="similar-drill__loading">正在加载同知识点练习题…</p>
      )}
      {!loading && !question && !error && !autoStart && (
        <button className="btn btn--primary btn--sm" onClick={() => loadOrGenerate(false)}>
          生成同知识点练习题
        </button>
      )}
      {question && (
        <>
          <div className="question-card__meta similar-drill__meta">
            <span className="badge badge--muted">{fromCache ? "已保存" : "AI 新生成"}</span>
            <span className="badge badge--muted">{question.question_type}</span>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => loadOrGenerate(true)}
              disabled={loading}
            >
              {loading ? "重新生成中…" : "重新生成"}
            </button>
          </div>
          <div className="mistake-card__stem">{question.stem}</div>
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
              className="btn btn--primary btn--sm"
              onClick={onSubmit}
              disabled={selected.length === 0 || submitting}
            >
              {submitting ? "提交中…" : "提交"}
            </button>
          ) : (
            <div
              className={`result-panel${result.is_correct ? " result-panel--correct" : " result-panel--wrong"}`}
            >
              <p
                className={`result-panel__title${result.is_correct ? " result-panel__title--correct" : " result-panel__title--wrong"}`}
              >
                {result.is_correct ? "回答正确" : "回答错误"}
              </p>
              <p>正确答案：{result.correct_answer.join("、")}</p>
              {result.explanation && <p>解析：{result.explanation}</p>}
            </div>
          )}
          <div className="similar-drill__actions">
            <button className="btn btn--danger btn--sm" onClick={onReportDelete}>
              报错删除
            </button>
            {result && onAdvance ? (
              <button className="btn btn--primary btn--sm" onClick={onAdvance}>
                下一道错题 →
              </button>
            ) : (
              <button className="btn btn--secondary btn--sm" onClick={onClose}>
                收起
              </button>
            )}
          </div>
        </>
      )}
      {error && (
        <p className="error-text" style={{ marginTop: 8 }}>
          {error}
          <button
            className="btn btn--secondary btn--sm"
            onClick={() => loadOrGenerate(false)}
            style={{ marginLeft: 8 }}
          >
            重试
          </button>
        </p>
      )}
    </div>
  );
}
