import { useEffect, useState } from "react";
import { confirmUpload, fetchKnowledgePoints, mediaUrl, uploadScreenshot } from "./api";
import type { ConfirmUploadBody, KnowledgePointBrief, UploadDraft } from "./types";

export default function UploadPage() {
  const [draft, setDraft] = useState<UploadDraft | null>(null);
  const [kps, setKps] = useState<KnowledgePointBrief[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const [stem, setStem] = useState("");
  const [questionType, setQuestionType] = useState<"单选" | "多选" | "判断">("单选");
  const [optionsText, setOptionsText] = useState("A. \nB. \nC. \nD. ");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [kpId, setKpId] = useState<number | "">("");

  useEffect(() => {
    fetchKnowledgePoints().then(setKps).catch(() => {});
  }, []);

  function parseOptions(text: string) {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const m = line.match(/^([A-Z]|对|错)[.、\s]\s*(.*)$/);
        if (!m) return null;
        return { key: m[1], text: m[2] || m[1] };
      })
      .filter(Boolean) as { key: string; text: string }[];
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    setDone(false);
    try {
      const d = await uploadScreenshot(file);
      setDraft(d);
      setStem(d.stem);
      setQuestionType(d.question_type as "单选" | "多选" | "判断");
      setOptionsText(
        d.options.map((o) => `${o.key}. ${o.text}`).join("\n") || "A. 对\nB. 错"
      );
      setAnswer(d.correct_answer.join(""));
      setExplanation(d.explanation || "");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function onConfirm() {
    if (!draft) return;
    const body: ConfirmUploadBody = {
      stem,
      question_type: questionType,
      options: parseOptions(optionsText),
      correct_answer: questionType === "多选"
        ? answer.toUpperCase().split("").filter((c) => /[A-Z]/.test(c))
        : [answer],
      explanation,
      knowledge_point_id: kpId === "" ? null : kpId,
    };
    setLoading(true);
    try {
      await confirmUpload(draft.id, body);
      setDone(true);
      setDraft(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <h2 className="page-title">上传错题截图</h2>
      <p className="page-desc">选择图片后 AI 自动识别，确认无误后入库并进错题本</p>

      {!draft && (
        <div className="upload-zone">
          <input type="file" accept="image/*" onChange={onFile} disabled={loading} />
          <div className="upload-zone__icon">📷</div>
          <p className="upload-zone__text">
            {loading ? "识别中，请稍候…" : "点击或拖拽上传错题截图"}
          </p>
        </div>
      )}

      {error && <p className="error-text" style={{ marginTop: 16 }}>{error}</p>}
      {done && (
        <div className="card" style={{ marginTop: 16, borderColor: "var(--success-border)", background: "var(--success-bg)" }}>
          <p className="success-text" style={{ margin: 0 }}>✓ 已入库，可在错题本查看</p>
        </div>
      )}

      {draft && (
        <div className="card" style={{ marginTop: 16 }}>
          <img
            src={mediaUrl(draft.image_path)}
            alt="上传原图"
            className="question-card__img"
          />
          <label className="form-label">题干</label>
          <textarea className="form-textarea" value={stem} onChange={(e) => setStem(e.target.value)} rows={3} />

          <label className="form-label">题型</label>
          <select className="form-select" value={questionType} onChange={(e) => setQuestionType(e.target.value as typeof questionType)}>
            <option value="单选">单选</option>
            <option value="多选">多选</option>
            <option value="判断">判断</option>
          </select>

          <label className="form-label">选项（每行一个，如 A. 内容）</label>
          <textarea className="form-textarea" value={optionsText} onChange={(e) => setOptionsText(e.target.value)} rows={4} />

          <label className="form-label">正确答案</label>
          <input className="form-input" value={answer} onChange={(e) => setAnswer(e.target.value)} />

          <label className="form-label">解析</label>
          <textarea className="form-textarea" value={explanation} onChange={(e) => setExplanation(e.target.value)} rows={3} />

          <label className="form-label">知识点（可选）</label>
          <select className="form-select" value={kpId} onChange={(e) => setKpId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">未选择</option>
            {kps.map((k) => (
              <option key={k.id} value={k.id}>{k.chapter} · {k.name}</option>
            ))}
          </select>

          <button className="btn btn--primary" onClick={onConfirm} disabled={loading || !stem} style={{ marginTop: 16 }}>
            {loading ? "入库中…" : "确认入库"}
          </button>
        </div>
      )}
    </div>
  );
}
