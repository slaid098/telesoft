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

  it("disables submit when URLs are empty", async () => {
    render(ReplaceLinkForm, { props: { channelId: 1 } });
    await fireEvent.input(screen.getByLabelText(/Pattern/i), {
      target: { value: "https://old\\.example\\.com" },
    });
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

  it("parses textarea URLs into an array and submits", async () => {
    mockPost.mockResolvedValue({ job_id: 5 });
    render(ReplaceLinkForm, { props: { channelId: 1 } });

    await fireEvent.input(screen.getByLabelText(/Post URLs/i), {
      target: { value: "https://t.me/a/1\nhttps://t.me/b/2\n\n" },
    });
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
        post_urls: ["https://t.me/a/1", "https://t.me/b/2"],
        pattern: "https://old\\.example\\.com",
        new_link: "https://new.example.com",
      });
    });
    await waitFor(() => {
      expect(mockGoto).toHaveBeenCalledWith("/jobs/5");
    });
  });
});
