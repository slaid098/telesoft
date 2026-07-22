import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

const onMessageHandlers: Set<(msg: { type: string; data: unknown }) => void> = new Set();

vi.mock("../lib/api", () => ({
  api: {
    get: mockGet,
    post: mockPost,
    put: vi.fn(),
    patch: vi.fn(),
    del: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    detail: unknown;
    constructor(status: number, detail: unknown, message: string) {
      super(message);
      this.status = status;
      this.detail = detail;
    }
  },
}));

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/jobs/1"), data: {} },
}));

vi.mock("../lib/ws", () => ({
  WebSocketClient: class {
    connect = vi.fn();
    close = vi.fn();
    send = vi.fn();
    isConnected = false;
    onMessage(handler: (msg: { type: string; data: unknown }) => void) {
      onMessageHandlers.add(handler);
      return () => onMessageHandlers.delete(handler);
    }
  },
}));

import type { Job, Log } from "../lib/types";
import JobDetailPage from "../routes/jobs/[id]/+page.svelte";

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 1,
    channel_id: 10,
    pattern: "https://old.example.com",
    new_link: "https://new.example.com",
    status: "running",
    total: 4,
    edited: 1,
    failed: 0,
    created_at: "2026-07-20T12:34:56Z",
    completed_at: null,
    ...overrides,
  };
}

function makeLog(overrides: Partial<Log> = {}): Log {
  return {
    id: 1,
    job_id: 1,
    message_id: 100,
    old_text: "hello https://old.example.com world",
    success: true,
    error: null,
    edited_at: "2026-07-20T12:35:00Z",
    ...overrides,
  };
}

function emitWsEvent(type: string, data: Record<string, unknown>): void {
  for (const handler of onMessageHandlers) {
    handler({ type, data });
  }
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  onMessageHandlers.clear();
});

describe("Job detail page", () => {
  it("renders job header, status badge, progress, and logs", () => {
    const job = makeJob();
    const logs = [makeLog()];
    render(JobDetailPage, { props: { data: { job, logs } } });

    expect(screen.getByText(/Задача #1/)).toBeTruthy();
    expect(screen.getByText(/Выполняется/)).toBeTruthy();
    expect(screen.getByText(/Прогресс: 1\/4/)).toBeTruthy();
    expect(screen.getByText("100")).toBeTruthy();
  });

  it("calls POST /api/jobs/{id}/cancel when Cancel button is clicked", async () => {
    mockPost.mockResolvedValue({ job_id: 1, status: "cancelled" });
    mockGet.mockResolvedValue(makeJob({ status: "cancelled" }));

    const job = makeJob();
    render(JobDetailPage, { props: { data: { job, logs: [] } } });

    await fireEvent.click(screen.getByRole("button", { name: /Отменить задачу/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/jobs/1/cancel");
    });
  });

  it("updates progress when a WS progress event arrives", async () => {
    const job = makeJob({ edited: 1, total: 4 });
    render(JobDetailPage, { props: { data: { job, logs: [] } } });

    expect(screen.getByText(/Прогресс: 1\/4/)).toBeTruthy();

    emitWsEvent("progress", { job_id: 1, edited: 3, failed: 0, total: 4 });

    await waitFor(() => {
      expect(screen.getByText(/Прогресс: 3\/4/)).toBeTruthy();
    });
  });

  it("refetches logs when a WS completed event arrives", async () => {
    const job = makeJob();
    const firstLogs = [makeLog({ id: 1, message_id: 100 })];
    const secondLogs = [makeLog({ id: 1, message_id: 100 }), makeLog({ id: 2, message_id: 101 })];

    mockGet.mockImplementation((path: string) => {
      if (path === "/api/jobs/1/logs") {
        return Promise.resolve({ logs: secondLogs, total: 2 });
      }
      return Promise.resolve(makeJob({ status: "done", edited: 4 }));
    });

    render(JobDetailPage, { props: { data: { job, logs: firstLogs } } });

    emitWsEvent("completed", { job_id: 1, edited: 4, failed: 0, total: 4 });

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/jobs/1/logs");
    });
    await waitFor(() => {
      expect(screen.getByText("101")).toBeTruthy();
    });
  });

  it("ignores WS events for other job ids", async () => {
    const job = makeJob();
    render(JobDetailPage, { props: { data: { job, logs: [] } } });

    emitWsEvent("progress", { job_id: 999, edited: 2, total: 5 });

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.getByText(/Прогресс: 1\/4/)).toBeTruthy();
  });
});
