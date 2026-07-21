import { browser } from "$app/environment";
import { goto } from "$app/navigation";
import type {
  PatternCreateRequest,
  PatternListResponse,
  PatternResponse,
  PreviewRequest,
  PreviewResponse,
  ReplaceLinkRequest,
} from "$lib/types";

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

type QueryValue = string | number | boolean | undefined | null;
type RequestOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, QueryValue>;
  headers?: Record<string, string>;
};

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, headers = {} } = options;
  const url = buildUrl(path, query);

  const init: RequestInit = {
    method,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const response = await fetch(url, init);

  if (response.status === 401 && browser) {
    const current = window.location.pathname;
    if (current !== "/login") {
      await goto(`/login?redirectTo=${encodeURIComponent(current)}`);
    }
    throw new ApiError(401, null, "Unauthorized");
  }

  const text = await response.text();
  const parsed = text ? (JSON.parse(text) as unknown) : null;

  if (!response.ok) {
    const message =
      parsed && typeof parsed === "object" && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, parsed, message);
  }

  return parsed as T;
}

export const api = {
  get: <T>(path: string, query?: Record<string, QueryValue>) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export type ApiClient = typeof api;

export async function previewReplace(
  channelId: number,
  payload: PreviewRequest,
): Promise<PreviewResponse> {
  return api.post<PreviewResponse>(`/api/channels/${channelId}/preview-replace`, payload);
}

export async function listPatterns(): Promise<PatternListResponse> {
  return api.get<PatternListResponse>("/api/patterns");
}

export async function createPattern(payload: PatternCreateRequest): Promise<PatternResponse> {
  return api.post<PatternResponse>("/api/patterns", payload);
}

export async function deletePattern(id: number): Promise<void> {
  await api.del<void>(`/api/patterns/${id}`);
}

export async function replaceLink(
  channelId: number,
  payload: ReplaceLinkRequest,
): Promise<{ job_id: number }> {
  return api.post<{ job_id: number }>(`/api/channels/${channelId}/replace-link`, payload);
}
