import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockPost, mockGoto } = vi.hoisted(() => ({
  mockPost: vi.fn(),
  mockGoto: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  api: {
    get: vi.fn(),
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
  listPatterns: vi.fn().mockResolvedValue({ patterns: [], total: 0 }),
  createPattern: vi.fn(),
  deletePattern: vi.fn(),
  previewReplace: vi.fn(),
  replaceLink: vi.fn(),
}));

vi.mock("$app/navigation", () => ({ goto: mockGoto }));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/channels/1"), data: {} },
}));

import ReplaceLinkForm from "../lib/components/ReplaceLinkForm.svelte";
import { replaceLink } from "../lib/api";

beforeEach(() => {
  mockPost.mockReset();
  mockGoto.mockReset();
  vi.mocked(replaceLink).mockReset();
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

  it("enables submit when simple-mode fields are filled", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
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

    const limitInput = screen.getByLabelText(/Limit/i);
    const button = screen.getByRole("button", { name: /Запустить/i }) as HTMLButtonElement;

    await fireEvent.input(limitInput, { target: { value: "0" } });
    expect(button.disabled).toBe(true);

    await fireEvent.input(limitInput, { target: { value: "1001" } });
    expect(button.disabled).toBe(true);
  });

  it("opens form with default limit 100", () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const limitInput = screen.getByLabelText(/Limit/i) as HTMLInputElement;
    expect(limitInput.value).toBe("100");
  });

  it("submits with pattern, new_link, mode and keep_tail", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 5 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });

    const form = screen.getByRole("button", { name: /Запустить/i }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledWith(1, {
        pattern: "https://t.me/bot?start=flow-*",
        new_link: "https://new.example.com",
        limit: 100,
        mode: "simple",
        keep_tail: false,
      });
    });
    await waitFor(() => {
      expect(mockGoto).toHaveBeenCalledWith("/jobs/5");
    });
  });

  it("sends keep_tail=true when checkbox is checked", async () => {
    vi.mocked(replaceLink).mockResolvedValue({ job_id: 7 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Найти ссылки/i), {
      target: { value: "https://t.me/bot?start=flow-*" },
    });
    await fireEvent.input(screen.getByLabelText(/Заменить на/i), {
      target: { value: "https://new.example.com" },
    });
    const keepTail = screen.getByLabelText(/Сохранить хвост/i);
    await fireEvent.click(keepTail);

    const form = screen.getByRole("button", { name: /Запустить/i }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(replaceLink).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ keep_tail: true, mode: "simple" }),
      );
    });
  });

  it("switches to Advanced mode", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const advancedTab = screen.getByRole("tab", { name: /Advanced/i });
    await fireEvent.click(advancedTab);
    expect(screen.getByLabelText(/Pattern \(raw regex\)/i)).toBeTruthy();
  });
});