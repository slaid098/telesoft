import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet, mockDel } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockDel: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  api: {
    get: mockGet,
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    del: mockDel,
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
  page: { url: new URL("http://localhost/channels"), data: {} },
}));

import type { Channel } from "../lib/types";
import ChannelsPage from "../routes/channels/+page.svelte";

function makeChannel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: 1,
    telegram_id: -1001234567890,
    title: "Test channel",
    username: "testchannel",
    is_active: true,
    added_at: "2026-07-20T12:34:56Z",
    ...overrides,
  };
}

beforeEach(() => {
  mockGet.mockReset();
  mockDel.mockReset();
});

describe("Channels page", () => {
  it("renders rows with title, telegram_id, and active badge", () => {
    const channels = [
      makeChannel({ id: 1, title: "alpha", is_active: true }),
      makeChannel({ id: 2, title: "beta", is_active: false }),
    ];
    render(ChannelsPage, { props: { data: { channels, total: 2 } } });

    expect(screen.getByText("alpha")).toBeTruthy();
    expect(screen.getByText("beta")).toBeTruthy();
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByText("inactive")).toBeTruthy();
  });

  it("renders empty state when there are no channels", () => {
    render(ChannelsPage, { props: { data: { channels: [], total: 0 } } });
    expect(screen.getByText(/No channels/i)).toBeTruthy();
  });

  it("calls DELETE /api/channels/{id} when Delete is clicked", async () => {
    mockDel.mockResolvedValue(null);
    const channels = [makeChannel({ id: 7, title: "alpha" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    window.confirm = vi.fn(() => true);
    mockGet.mockResolvedValue({ channels: [], total: 0 });
    await fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith("/api/channels/7");
    });
  });
});
