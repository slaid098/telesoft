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
  pending: "Pending",
  running: "Running",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
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

export type ReplaceLinkRequest = {
  post_urls: string[];
  pattern: string;
  new_link: string;
};

export type WsEvent = {
  type: "job_started" | "progress" | "completed" | "failed" | "cancelled";
  job_id: number;
  edited?: number;
  failed?: number;
  total?: number;
  message_id?: number;
  error?: string;
};
