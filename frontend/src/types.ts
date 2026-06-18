export type Option = { key: string; text: string };

export type Question = {
  id: number;
  stem: string;
  question_type: "单选" | "多选" | "判断";
  options: Option[];
  images: string[];
  exam_point: string | null;
  year: string | null;
  knowledge_point_name?: string | null;
  source?: string | null;
};

export type AttemptResult = {
  is_correct: boolean;
  correct_answer: string[];
  explanation: string | null;
};

export type Mistake = {
  question_id: number;
  stem: string;
  question_type: string;
  exam_point: string | null;
  year: string | null;
  wrong_answer: string[];
  correct_answer: string[];
  wrong_count: number;
  correct_count: number;
  first_wrong_at: string;
  last_attempt_at: string;
  mastery: string;
  favorite: boolean;
  knowledge_point_name?: string | null;
  images?: string[];
};

export type Weakness = {
  knowledge_point_id: number;
  name: string;
  chapter: string;
  mastery_requirement: string | null;
  attempt_count: number;
  correct_count: number;
  wrong_count: number;
  mistake_count: number;
  accuracy: number | null;
  last_attempt_at: string | null;
  priority: number;
  tags: string[];
};

export type DailyTaskSummary = {
  task_date: string;
  target_count: number;
  total: number;
  completed: number;
};

export type DailyTaskQuestion = Question & { completed: boolean };

export type AppSettings = { daily_target_count: number };

export type KnowledgePointBrief = {
  id: number;
  name: string;
  chapter: string;
  mastery_requirement: string | null;
};

export type UploadDraft = {
  id: number;
  image_path: string;
  confidence: number | null;
  stem: string;
  question_type: "单选" | "多选" | "判断";
  options: Option[];
  correct_answer: string[];
  explanation: string | null;
  chapter: string | null;
  exam_point: string | null;
};

export type ConfirmUploadBody = {
  stem: string;
  question_type: string;
  options: Option[];
  correct_answer: string[];
  explanation?: string | null;
  chapter?: string | null;
  exam_point?: string | null;
  knowledge_point_id?: number | null;
};
