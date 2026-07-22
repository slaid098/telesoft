import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet, mockDel, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockDel: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  api: {
    get: mockGet,
    post: mockPost,
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

import ChannelForm from "../lib/components/ChannelForm.svelte";
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
  mockPost.mockReset();
});

describe("Channels page", () => {
  it("renders rows with title, telegram_id, and active badge", () => {
    const channels = [
      makeChannel({ id: 1, title: "alpha", is_active: true }),
      makeChannel({ id: 2, title: "beta", is_active: false }),
    ];
    render(ChannelsPage, { props: { data: { channels, total: 2 } } });

    expect(screen.getAllByText("alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("beta").length).toBeGreaterThan(0);
    expect(screen.getAllByText("активен").length).toBeGreaterThan(0);
    expect(screen.getAllByText("неактивен").length).toBeGreaterThan(0);
  });

  it("renders empty state when there are no channels", () => {
    render(ChannelsPage, { props: { data: { channels: [], total: 0 } } });
    expect(screen.getAllByText(/Нет каналов/i).length).toBeGreaterThan(0);
  });

  it("calls DELETE /api/channels/{id} when Delete is clicked", async () => {
    mockDel.mockResolvedValue(null);
    const channels = [makeChannel({ id: 7, title: "alpha" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    window.confirm = vi.fn(() => true);
    mockGet.mockResolvedValue({ channels: [], total: 0 });
    const deleteButtons = screen.getAllByRole("button", { name: "Удалить" });
    await fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith("/api/channels/7");
    });
  });

  it("opens Add channel form when Add channel button is clicked", async () => {
    render(ChannelsPage, { props: { data: { channels: [], total: 0 } } });
    const addButton = screen.getByRole("button", { name: /Добавить канал/i });
    await fireEvent.click(addButton);
    expect(screen.getByLabelText(/Telegram ID/i)).toBeTruthy();
    expect(screen.getByLabelText(/Название/i)).toBeTruthy();
  });

  it("submits Add channel form and refreshes the list", async () => {
    const created = makeChannel({ id: 42, title: "fresh" });
    mockPost.mockResolvedValue(created);
    mockGet.mockResolvedValue({ channels: [created], total: 1 });

    render(ChannelsPage, { props: { data: { channels: [], total: 0 } } });

    await fireEvent.click(screen.getByRole("button", { name: /Добавить канал/i }));

    const tgInput = screen.getByLabelText(/Telegram ID/i);
    const titleInput = screen.getByLabelText(/Название/i);
    await fireEvent.input(tgInput, { target: { value: "-1001234567890" } });
    await fireEvent.input(titleInput, { target: { value: "fresh" } });

    const form = screen.getByRole("button", { name: "Сохранить" }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/channels", {
        telegram_id: -1001234567890,
        title: "fresh",
      });
    });
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("/api/channels");
    });
  });

  it("hides Add channel form on Cancel", async () => {
    render(ChannelsPage, { props: { data: { channels: [], total: 0 } } });
    await fireEvent.click(screen.getByRole("button", { name: /Добавить канал/i }));
    expect(screen.getByLabelText(/Telegram ID/i)).toBeTruthy();

    await fireEvent.click(screen.getByRole("button", { name: /Отмена/i }));
    expect(screen.queryByLabelText(/Telegram ID/i)).toBeNull();
  });
});

describe("ChannelForm", () => {
  it("disables Save button when fields are empty", () => {
    render(ChannelForm, { props: { onSaved: vi.fn(), onCancel: vi.fn() } });
    const saveButton = screen.getByRole("button", { name: /Сохранить/i }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });

  it("enables Save when telegram_id and title are filled", async () => {
    render(ChannelForm, { props: { onSaved: vi.fn(), onCancel: vi.fn() } });
    await fireEvent.input(screen.getByLabelText(/Telegram ID/i), {
      target: { value: "-1001234567890" },
    });
    await fireEvent.input(screen.getByLabelText(/Название/i), { target: { value: "alpha" } });
    const saveButton = screen.getByRole("button", { name: /Сохранить/i }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(false);
  });

  it("calls onSaved after a successful POST", async () => {
    const saved: Channel = makeChannel({ id: 99, title: "echo" });
    mockPost.mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(ChannelForm, { props: { onSaved, onCancel: vi.fn() } });
    await fireEvent.input(screen.getByLabelText(/Telegram ID/i), {
      target: { value: "-1001234567890" },
    });
    await fireEvent.input(screen.getByLabelText(/Название/i), { target: { value: "echo" } });

    const form = screen.getByRole("button", { name: "Сохранить" }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/channels", {
        telegram_id: -1001234567890,
        title: "echo",
      });
    });
    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(saved);
    });
  });
});
