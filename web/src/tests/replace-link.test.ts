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
}));

vi.mock("$app/navigation", () => ({ goto: mockGoto }));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/channels/1"), data: {} },
}));

import ReplaceLinkForm from "../lib/components/ReplaceLinkForm.svelte";

beforeEach(() => {
  mockPost.mockReset();
  mockGoto.mockReset();
});

describe("ReplaceLinkForm", () => {
  it("disables submit when fields are empty", () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    const button = screen.getByRole("button", { name: /Run replace-link/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("disables submit when pattern is empty", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/New link/i), {
      target: { value: "https://new.example.com" },
    });
    const button = screen.getByRole("button", { name: /Run replace-link/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("shows error on invalid regex pattern", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Pattern/i), {
      target: { value: "(" },
    });
    expect(await screen.findByText(/Invalid regex/i)).toBeTruthy();
  });

  it("disables submit when limit is out of range", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Pattern/i), {
      target: { value: "https://old\\.example\\.com" },
    });
    await fireEvent.input(screen.getByLabelText(/New link/i), {
      target: { value: "https://new.example.com" },
    });

    const limitInput = screen.getByLabelText(/Limit/i);
    const button = screen.getByRole("button", { name: /Run replace-link/i }) as HTMLButtonElement;

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

  it("submits with pattern, new_link and limit", async () => {
    mockPost.mockResolvedValue({ job_id: 5 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Pattern/i), {
      target: { value: "https://old\\.example\\.com" },
    });
    await fireEvent.input(screen.getByLabelText(/New link/i), {
      target: { value: "https://new.example.com" },
    });

    const form = screen.getByRole("button", { name: /Run replace-link/i }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/channels/1/replace-link", {
        pattern: "https://old\\.example\\.com",
        new_link: "https://new.example.com",
        limit: 100,
      });
    });
    await waitFor(() => {
      expect(mockGoto).toHaveBeenCalledWith("/jobs/5");
    });
  });
});
