export type AuthUser = { username: string };
export type MeResponse = { user: string };
export type OkResponse = { status: string };

export type Channel = {
  id: number;
  telegram_id: number;
  title: string;
  username: string | null;
  is_active: boolean;
  added_at: string;
};

export type ChannelCreate = {
  telegram_id: number;
  title: string;
  username?: string;
};

export type ChannelUpdate = {
  title?: string;
  username?: string;
  is_active?: boolean;
};

export type ChannelListResponse = {
  channels: Channel[];
  total: number;
};

export type JobStatus = "pending" | "running" | "done" | "failed" | "cancelled";

export const JOB_STATUSES: JobStatus[] = ["pending", "running", "done", "failed", "cancelled"];

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Ожидает",
  running: "Выполняется",
  done: "Готово",
  failed: "Ошибка",
  cancelled: "Отменена",
};

export type Job = {
  id: number;
  channel_id: number;
  pattern: string;
  new_link: string;
  status: JobStatus;
  total: number;
  edited: number;
  failed: number;
  created_at: string;
  completed_at: string | null;
};

export type JobListResponse = {
  jobs: Job[];
  total: number;
};

export type Log = {
  id: number;
  job_id: number;
  message_id: number;
  old_text: string | null;
  success: boolean;
  error: string | null;
  edited_at: string;
};

export type LogListResponse = {
  logs: Log[];
  total: number;
};

export type ReplaceMode = "simple" | "library" | "advanced";

export type ReplaceLinkRequest = {
  pattern: string;
  new_link: string;
  post_link: string;
  limit: number;
  mode: ReplaceMode;
  full_replace: boolean;
};

export type PreviewRequest = {
  pattern: string;
  new_link: string;
  post_link: string;
  mode: ReplaceMode;
  full_replace: boolean;
  limit: number;
};

export type PreviewItem = {
  message_id: number;
  before: string;
  after: string;
  match_source: "text" | "entity";
};

export type PreviewResponse = {
  previews: PreviewItem[];
  total_matches: number;
  compiled_pattern: string;
};

export type PatternResponse = {
  id: number;
  name: string;
  pattern: string;
  description: string | null;
  is_builtin: boolean;
  created_at: string;
};

export type PatternListResponse = {
  patterns: PatternResponse[];
  total: number;
};

export type PatternCreateRequest = {
  name: string;
  pattern: string;
  description?: string;
};

export type WsEventType = "job_started" | "progress" | "completed" | "failed" | "cancelled";

export type WsEvent = {
  type: WsEventType;
  job_id: number;
  edited?: number;
  failed?: number;
  total?: number;
  message_id?: number;
  error?: string;
};

export type WsEventPayload = {
  job_id?: number;
  edited?: number;
  failed?: number;
  total?: number;
  message_id?: number;
  error?: string;
  status?: string;
};
