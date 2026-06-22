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

  const [subject, setSubject] = useState("");



  useEffect(() => {

    fetchKnowledgePoints().then(setKps).catch(() => {});

  }, []);



  const filteredKps = subject

    ? kps.filter((k) => k.subject === subject)

    : kps;



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



  function applyDraft(d: UploadDraft) {

    setDraft(d);

    setStem(d.stem);

    setQuestionType(d.question_type as "单选" | "多选" | "判断");

    setOptionsText(

      d.options.map((o) => `${o.key}. ${o.text}`).join("\n") || "A. 对\nB. 错"

    );

    setAnswer(d.correct_answer.join(""));

    setExplanation(d.explanation || "");

    setSubject(d.subject || "");

    setKpId(d.knowledge_point_id ?? "");

  }



  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {

    const file = e.target.files?.[0];

    if (!file) return;

    setLoading(true);

    setError(null);

    setDone(false);

    try {

      applyDraft(await uploadScreenshot(file));

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

      chapter: draft.chapter,

      exam_point: draft.exam_point,

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

      <p className="page-desc">

        上传网课/讲义截图后：先 OCR 转写 → 文本润色整理 → AI 归档科目与知识点；缺答案或解析会自动补全。确认后入库并进错题本。

      </p>



      {!draft && (

        <div className="upload-zone">

          <input type="file" accept="image/*" onChange={onFile} disabled={loading} />

          <div className="upload-zone__icon">📷</div>

          <p className="upload-zone__text">

            {loading ? "识别、润色并归档中，请稍候…" : "点击或拖拽上传错题截图"}

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



          {(draft.subject || draft.needs_review || draft.text_polished || draft.answer_inferred || draft.explanation_generated) && (
            <div className="question-card__meta" style={{ marginBottom: 16 }}>
              {draft.subject && <span className="badge">{draft.subject}</span>}
              {draft.text_polished && (
                <span className="badge badge--success">文字已润色</span>
              )}
              {draft.answer_inferred && (
                <span className="badge badge--warning">答案为 AI 补充</span>
              )}
              {draft.explanation_generated && (
                <span className="badge badge--warning">解析为 AI 生成</span>
              )}
              {draft.needs_review && (
                <span className="badge badge--muted">归类待核对</span>
              )}
            </div>
          )}



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



          <label className="form-label">知识点</label>

          <select className="form-select" value={kpId} onChange={(e) => setKpId(e.target.value ? Number(e.target.value) : "")}>

            <option value="">未选择</option>

            {filteredKps.map((k) => (

              <option key={k.id} value={k.id}>

                {k.chapter} · {k.name}

              </option>

            ))}

          </select>

          {draft.classify_note && (

            <p className="page-desc" style={{ marginTop: 8, marginBottom: 0 }}>

              归类说明：{draft.classify_note}

              {draft.classify_confidence != null && `（置信度 ${(draft.classify_confidence * 100).toFixed(0)}%）`}

            </p>

          )}



          <button className="btn btn--primary" onClick={onConfirm} disabled={loading || !stem} style={{ marginTop: 16 }}>

            {loading ? "入库中…" : "确认入库"}

          </button>

        </div>

      )}

    </div>

  );

}


