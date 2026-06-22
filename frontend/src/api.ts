const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function apiFetch(path: string, init?: RequestInit) {
  const r = await fetch(`${API_BASE}${path}`, init);
  return r;
}

export async function fetchDailyTask() {
  const r = await apiFetch("/daily-task");
  if (!r.ok) throw new Error(`加载今日任务失败：HTTP ${r.status}`);
  return r.json() as Promise<import("./types").DailyTaskSummary>;
}

export async function fetchDailyTaskQuestions(): Promise<import("./types").DailyTaskQuestion[]> {
  const r = await apiFetch("/daily-task/questions");
  if (!r.ok) throw new Error(`加载今日题目失败：HTTP ${r.status}`);
  return r.json();
}

export async function fetchSettings(): Promise<import("./types").AppSettings> {
  const r = await apiFetch("/settings");
  if (!r.ok) throw new Error(`加载设置失败：HTTP ${r.status}`);
  return r.json();
}

export async function updateSettings(dailyTargetCount: number): Promise<import("./types").AppSettings> {
  const r = await apiFetch("/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ daily_target_count: dailyTargetCount }),
  });
  if (!r.ok) throw new Error(`保存设置失败：HTTP ${r.status}`);
  return r.json();
}

export async function fetchQuestions(
  limit = 10,
  subject?: string
): Promise<import("./types").Question[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (subject) params.set("subject", subject);
  const r = await apiFetch(`/questions?${params.toString()}`);
  if (!r.ok) throw new Error(`取题失败：HTTP ${r.status}`);
  return r.json();
}

export async function submitAttempt(
  questionId: number,
  userAnswer: string[]
): Promise<import("./types").AttemptResult> {
  const r = await apiFetch("/attempts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, user_answer: userAnswer }),
  });
  if (!r.ok) throw new Error(`提交失败：HTTP ${r.status}`);
  return r.json();
}

export async function fetchMistakes(favoriteOnly = false): Promise<import("./types").Mistake[]> {
  const q = favoriteOnly ? "?favorite_only=true" : "";
  const r = await apiFetch(`/mistakes${q}`);
  if (!r.ok) throw new Error(`加载错题本失败：HTTP ${r.status}`);
  return r.json();
}

export async function toggleMistakeFavorite(questionId: number): Promise<boolean> {
  const r = await apiFetch(`/mistakes/${questionId}/favorite`, { method: "POST" });
  if (!r.ok) throw new Error(`收藏操作失败：HTTP ${r.status}`);
  const data = await r.json();
  return data.favorite as boolean;
}

export async function fetchWeaknesses(): Promise<import("./types").Weakness[]> {
  const r = await apiFetch("/weaknesses");
  if (!r.ok) throw new Error(`加载薄弱点失败：HTTP ${r.status}`);
  return r.json();
}

export async function fetchSimilar(
  questionId: number
): Promise<import("./types").Question | null> {
  const r = await apiFetch(`/questions/${questionId}/similar`);
  if (r.status === 404) return null;
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `加载失败：HTTP ${r.status}`);
  }
  return r.json();
}

export type SimilarQuestion = import("./types").Question & {
  cached?: boolean;
  origin_question_id?: number;
};

export async function generateSimilar(
  questionId: number,
  regenerate = false
): Promise<SimilarQuestion> {
  const q = regenerate ? "?regenerate=true" : "";
  const r = await apiFetch(`/questions/${questionId}/similar${q}`, { method: "POST" });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `生成失败：HTTP ${r.status}`);
  }
  return r.json();
}

export async function deleteQuestion(questionId: number): Promise<void> {
  const r = await apiFetch(`/questions/${questionId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`删除失败：HTTP ${r.status}`);
}

export async function fetchKnowledgePoints(): Promise<import("./types").KnowledgePointBrief[]> {
  const r = await apiFetch("/knowledge-points");
  if (!r.ok) throw new Error(`加载知识点失败：HTTP ${r.status}`);
  return r.json();
}

export async function uploadScreenshot(file: File): Promise<import("./types").UploadDraft> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch("/uploads", { method: "POST", body: fd });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || `上传失败：HTTP ${r.status}`);
  }
  return r.json();
}

export async function confirmUpload(
  draftId: number,
  body: import("./types").ConfirmUploadBody
): Promise<number> {
  const r = await apiFetch(`/uploads/${draftId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`确认入库失败：HTTP ${r.status}`);
  const data = await r.json();
  return data.question_id as number;
}

export function mediaUrl(path: string) {
  if (path.startsWith("http")) return path;
  const base = import.meta.env.VITE_API_BASE
    ? import.meta.env.VITE_API_BASE.replace(/\/$/, "")
    : "";
  return `${base}/media/${path}`;
}
