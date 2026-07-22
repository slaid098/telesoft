import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGoto } = vi.hoisted(() => ({
  mockGoto: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
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
  apiErrorMessage: (err: unknown, fallback: string): string => {
    if (err instanceof Error) {
      return err.message || fallback;
    }
    return "Network error";
  },
  listPatterns: vi.fn(),
  createPattern: vi.fn(),
  deletePattern: vi.fn(),
  previewReplace: vi.fn(),
  replaceLink: vi.fn(),
}));

vi.mock("$app/navigation", () => ({ goto: mockGoto }));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/channels/1"), data: {} },
}));

import { listPatterns, previewReplace, replaceLink } from "../lib/api";
import PatternLibrary from "../lib/components/PatternLibrary.svelte";
import PreviewModal from "../lib/components/PreviewModal.svelte";
import ReplaceLinkForm from "../lib/components/ReplaceLinkForm.svelte";
import type { PreviewResponse } from "../lib/types";

beforeEach(() => {
  mockGoto.mockReset();
  vi.mocked(replaceLink).mockReset();
  vi.mocked(previewReplace).mockReset();
  vi.mocked(listPatterns).mockReset();
});

describe("ReplaceLinkForm", () => {
  it("disables submit when fields are empty", () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("disables submit when new link is empty", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("disables submit when post link is empty", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("enables submit when simple-mode fields are filled", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("disables submit when limit is out of range", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });

    const limitInput = screen.getByLabelText(/Лимит/i);
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;

    await fireEvent.input(limitInput, { target: { value: "0" } });
    expect(button.disabled).toBe(true);

    await fireEvent.input(limitInput, { target: { value: "1001" } });
    expect(button.disabled).toBe(true);
  });

  it("opens form with default limit 100", () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const limitInput = screen.getByLabelText(/Лимит/i) as HTMLInputElement;
    expect(limitInput.value).toBe("100");
  });

  it("submits with pattern, new_link, post_link, mode and full_replace", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 5 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });

    const form = screen.getByRole("button", { name: /Запустить/i }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledWith(1, {
        pattern: "https://t.me/bot?start=flow-*",
        new_link: "https://new.example.com",
        post_link: "https://t.me/test/140",
        limit: 100,
        mode: "simple",
        full_replace: true,
      });
    });
    await waitFor(() => {
      expect(mockGoto).toHaveBeenCalledWith("/jobs/5");
    });
  });

  it("sends full_replace=false when partial radio is selected", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 7 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });
    const partialRadio = screen.getByRole("radio", { name: /Частичная/i });
    await fireEvent.click(partialRadio);

    const form = screen.getByRole("button", { name: /Запустить/i }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          full_replace: false,
          mode: "simple",
          post_link: "https://t.me/test/140",
        }),
      );
    });
  });

  it("defaults to full_replace=true (Полная замена radio checked)", () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const fullRadio = screen.getByRole("radio", { name: /Полная замена/i }) as HTMLInputElement;
    const partialRadio = screen.getByRole("radio", { name: /Частичная/i }) as HTMLInputElement;
    expect(fullRadio.checked).toBe(true);
    expect(partialRadio.checked).toBe(false);
  });

  it("switches to Advanced mode", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const advancedTab = screen.getByRole("tab", { name: /Расширенный/i });
    await fireEvent.click(advancedTab);
    expect(screen.getByLabelText(/Паттерн \(регулярное выражение\)/i)).toBeTruthy();
  });

  it("preview button calls previewReplace and opens modal", async () => {
    const previewResp: PreviewResponse = {
      previews: [
        {
          message_id: 42,
          before: "https://old.example.com/path",
          after: "https://new.example.com/path",
          match_source: "text",
        },
      ],
      total_matches: 1,
      compiled_pattern: "https://old\\.example\\.com",
    };
    vi.mocked(previewReplace).mockResolvedValue(previewResp);
    const onPreview = vi.fn();

    render(ReplaceLinkForm, { props: { channelId: 1, onPreview } });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://old.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });

    const previewCheckbox = screen.getByLabelText(/Показать предпросмотр/i);
    await fireEvent.click(previewCheckbox);

    const previewBtn = screen.getByRole("button", { name: /Предпросмотр/i });
    await fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(previewReplace).toHaveBeenCalledWith(1, {
        pattern: "https://old.example.com",
        new_link: "https://new.example.com",
        post_link: "https://t.me/test/140",
        mode: "simple",
        full_replace: true,
        limit: 100,
      });
    });
    await waitFor(() => {
      expect(onPreview).toHaveBeenCalledWith(previewResp);
    });
  });

  it("runNonce > 0 triggers submitJob once", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 11 });
    const { rerender } = render(ReplaceLinkForm, {
      props: { channelId: 1, runNonce: 0 },
    });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });

    rerender({ channelId: 1, runNonce: 1 });

    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledTimes(1);
    });
    expect(replaceLink).toHaveBeenCalledWith(1, {
      pattern: "https://t.me/bot?start=flow-*",
      new_link: "https://new.example.com",
      post_link: "https://t.me/test/140",
      limit: 100,
      mode: "simple",
      full_replace: true,
    });
  });

  it("same runNonce does not trigger submitJob twice", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 12 });
    const { rerender } = render(ReplaceLinkForm, {
      props: { channelId: 1, runNonce: 0 },
    });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    await fireEvent.input(screen.getByLabelText(/Ссылка на последний пост/i), {
      target: { value: "https://t.me/test/140" },
    });

    rerender({ channelId: 1, runNonce: 5 });
    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledTimes(1);
    });

    rerender({ channelId: 1, runNonce: 5 });
    rerender({ channelId: 1, runNonce: 5 });

    await new Promise((r) => setTimeout(r, 50));
    expect(replaceLink).toHaveBeenCalledTimes(1);
  });
});

describe("PatternLibrary", () => {
  it("renders patterns from listPatterns", async () => {
    vi.mocked(listPatterns).mockResolvedValue({
      patterns: [
        {
          id: 1,
          name: "Bot start",
          pattern: "https://t\\.me/bot\\?start=flow-.*",
          description: "Bot deep-link pattern",
          is_builtin: true,
          created_at: "2026-07-20T12:34:56Z",
        },
        {
          id: 2,
          name: "Custom",
          pattern: "https://example\\.com/.*",
          description: null,
          is_builtin: false,
          created_at: "2026-07-20T12:34:57Z",
        },
      ],
      total: 2,
    });

    render(PatternLibrary, {
      props: { onClose: vi.fn(), onPatternsChanged: vi.fn() },
    });

    await waitFor(() => {
      expect(screen.getByText("Bot start")).toBeTruthy();
      expect(screen.getByText("Custom")).toBeTruthy();
      expect(screen.getByText("встроенный")).toBeTruthy();
    });
    cleanup();
  });
});

describe("PreviewModal", () => {
  it("shows before→after pairs", () => {
    render(PreviewModal, {
      props: {
        previews: [
          {
            message_id: 100,
            before: "https://old.example.com/a",
            after: "https://new.example.com/a",
            match_source: "text",
          },
          {
            message_id: 101,
            before: "https://old.example.com/b",
            after: "https://new.example.com/b",
            match_source: "entity",
          },
        ],
        totalMatches: 2,
        compiledPattern: "https://old\\.example\\.com",
        onRun: vi.fn(),
        onEdit: vi.fn(),
      },
    });

    expect(screen.getByText(/Пост #100/i)).toBeTruthy();
    expect(screen.getByText("https://old.example.com/a")).toBeTruthy();
    expect(screen.getByText("https://new.example.com/a")).toBeTruthy();
    expect(screen.getByText(/Пост #101/i)).toBeTruthy();
    expect(screen.getByText("https://old.example.com/b")).toBeTruthy();
    expect(screen.getByText("https://new.example.com/b")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    cleanup();
  });
});
