import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet, mockDel, mockPost, mockPatch } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockDel: vi.fn(),
  mockPost: vi.fn(),
  mockPatch: vi.fn(),
}));

const mockToggleChannelActive = vi.hoisted(() =>
  vi.fn(async (id: number, active: boolean) => {
    mockPatch(`/api/channels/${id}`, { is_active: active });
    return undefined;
  }),
);

const mockUpdateChannel = vi.hoisted(() =>
  vi.fn(async (id: number, payload: unknown) => {
    mockPatch(`/api/channels/${id}`, payload);
    return makeChannel({ id, ...(payload as object) });
  }),
);

vi.mock("../lib/api", () => ({
  api: {
    get: mockGet,
    post: mockPost,
    put: vi.fn(),
    patch: mockPatch,
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
  listChannels: mockGet,
  toggleChannelActive: mockToggleChannelActive,
  updateChannel: mockUpdateChannel,
  apiErrorMessage: (err: unknown, fallback: string) =>
    err instanceof Error ? err.message : fallback,
}));

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

vi.mock("$app/state", () => ({
  page: { url: new URL("http://localhost/channels"), data: {} },
}));

import ActionMenu from "../lib/components/ActionMenu.svelte";
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
  mockPatch.mockReset();
  mockUpdateChannel.mockReset();
  mockToggleChannelActive.mockReset();
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

  it("opens action menu when Actions button is clicked", async () => {
    const channels = [makeChannel({ id: 1, title: "alpha" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    const triggers = screen.getAllByRole("button", { name: "Действия с каналом" });
    expect(triggers.length).toBeGreaterThan(0);
    expect(screen.queryByText("Заменить ссылки")).toBeNull();

    await fireEvent.click(triggers[0]);

    await waitFor(() => {
      expect(screen.getByText("Заменить ссылки")).toBeTruthy();
      expect(screen.getByText("Редактировать")).toBeTruthy();
      expect(screen.getByText("Деактивировать")).toBeTruthy();
    });
  });

  it("closes action menu on Escape", async () => {
    const channels = [makeChannel({ id: 1, title: "alpha" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    const trigger = screen.getAllByRole("button", { name: "Действия с каналом" })[0];
    await fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByText("Редактировать")).toBeTruthy());

    await fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByText("Редактировать")).toBeNull();
    });
  });

  it("opens ReplaceLinkModal when Replace links is chosen", async () => {
    const channels = [makeChannel({ id: 7, title: "alpha" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Заменить ссылки"));

    await waitFor(() => {
      expect(screen.getByText("Замена ссылки")).toBeTruthy();
    });
  });

  it("opens EditChannelModal prefilled when Edit is chosen", async () => {
    const channels = [makeChannel({ id: 7, title: "alpha", username: "alphauser" })];
    render(ChannelsPage, { props: { data: { channels, total: 1 } } });

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Редактировать"));

    await waitFor(() => {
      const titleInput = screen.getByLabelText(/Название/i) as HTMLInputElement;
      expect(titleInput.value).toBe("alpha");
      const usernameInput = screen.getByLabelText(/Username/i) as HTMLInputElement;
      expect(usernameInput.value).toBe("alphauser");
    });
  });

  it("submits PATCH on edit and refreshes the list", async () => {
    const original = makeChannel({ id: 5, title: "old", username: "olduser" });
    const updated = makeChannel({ id: 5, title: "new", username: "newuser" });
    mockUpdateChannel.mockResolvedValue(updated);
    mockGet.mockResolvedValue({ channels: [updated], total: 1 });

    render(ChannelsPage, { props: { data: { channels: [original], total: 1 } } });

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Редактировать"));

    await waitFor(() => expect(screen.getByLabelText(/Название/i)).toBeTruthy());

    const titleInput = screen.getByLabelText(/Название/i) as HTMLInputElement;
    await fireEvent.input(titleInput, { target: { value: "new" } });
    const usernameInput = screen.getByLabelText(/Username/i) as HTMLInputElement;
    await fireEvent.input(usernameInput, { target: { value: "newuser" } });

    const form = screen.getByRole("button", { name: "Сохранить" }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(mockUpdateChannel).toHaveBeenCalledWith(5, {
        title: "new",
        username: "newuser",
      });
    });
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalled();
    });
  });

  it("calls PATCH is_active:false when Deactivate is chosen", async () => {
    const channel = makeChannel({ id: 3, title: "alpha", is_active: true });
    mockGet.mockResolvedValue({ channels: [], total: 0 });

    render(ChannelsPage, { props: { data: { channels: [channel], total: 1 } } });

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Деактивировать"));

    await waitFor(() => {
      expect(mockToggleChannelActive).toHaveBeenCalledWith(3, false);
    });
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalled();
    });
  });

  it("calls PATCH is_active:true when Activate is chosen", async () => {
    const channel = makeChannel({ id: 4, title: "alpha", is_active: false });
    mockGet.mockResolvedValue({ channels: [], total: 0 });

    render(ChannelsPage, { props: { data: { channels: [channel], total: 1 } } });

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Активировать"));

    await waitFor(() => {
      expect(mockToggleChannelActive).toHaveBeenCalledWith(4, true);
    });
  });

  it("calls DELETE when Delete is chosen (with confirm)", async () => {
    const channel = makeChannel({ id: 7, title: "alpha" });
    mockDel.mockResolvedValue(null);
    mockGet.mockResolvedValue({ channels: [], total: 0 });

    render(ChannelsPage, { props: { data: { channels: [channel], total: 1 } } });

    window.confirm = vi.fn(() => true);

    await fireEvent.click(screen.getAllByRole("button", { name: "Действия с каналом" })[0]);
    await fireEvent.click(screen.getByText("Удалить"));

    await waitFor(() => {
      expect(mockDel).toHaveBeenCalledWith("/api/channels/7");
    });
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalled();
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
      expect(mockGet).toHaveBeenCalled();
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

describe("ActionMenu", () => {
  it("shows Activate label for inactive channel", async () => {
    const channel = makeChannel({ id: 1, is_active: false });
    render(ActionMenu, { props: { channel } });

    await fireEvent.click(screen.getByRole("button", { name: "Действия с каналом" }));
    await waitFor(() => {
      expect(screen.getByText("Активировать")).toBeTruthy();
    });
  });

  it("shows Deactivate label for active channel", async () => {
    const channel = makeChannel({ id: 1, is_active: true });
    render(ActionMenu, { props: { channel } });

    await fireEvent.click(screen.getByRole("button", { name: "Действия с каналом" }));
    await waitFor(() => {
      expect(screen.getByText("Деактивировать")).toBeTruthy();
    });
  });

  it("closes menu after selecting an action", async () => {
    const channel = makeChannel({ id: 1, is_active: true });
    const onEdit = vi.fn();
    render(ActionMenu, { props: { channel, onEdit } });

    await fireEvent.click(screen.getByRole("button", { name: "Действия с каналом" }));
    await fireEvent.click(screen.getByText("Редактировать"));

    expect(onEdit).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByText("Редактировать")).toBeNull();
    });
  });

  it("closes menu on click outside", async () => {
    const channel = makeChannel({ id: 1, is_active: true });
    render(ActionMenu, { props: { channel } });

    const trigger = screen.getByRole("button", { name: "Действия с каналом" });
    await fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByText("Редактировать")).toBeTruthy());

    await fireEvent.click(document.body);

    await waitFor(() => {
      expect(screen.queryByText("Редактировать")).toBeNull();
    });
  });
});

describe("ChannelForm", () => {
  it("disables Save button when fields are empty (create mode)", () => {
    render(ChannelForm, { props: { onSaved: vi.fn(), onCancel: vi.fn() } });
    const saveButton = screen.getByRole("button", { name: /Сохранить/i }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });

  it("enables Save when telegram_id and title are filled (create mode)", async () => {
    render(ChannelForm, { props: { onSaved: vi.fn(), onCancel: vi.fn() } });
    await fireEvent.input(screen.getByLabelText(/Telegram ID/i), {
      target: { value: "-1001234567890" },
    });
    await fireEvent.input(screen.getByLabelText(/Название/i), { target: { value: "alpha" } });
    const saveButton = screen.getByRole("button", { name: /Сохранить/i }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(false);
  });

  it("calls onSaved after a successful POST (create mode)", async () => {
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

  it("prefills title and username in edit mode", () => {
    const channel = makeChannel({ id: 5, title: "edited", username: "editeduser" });
    render(ChannelForm, { props: { channel, onSaved: vi.fn(), onCancel: vi.fn() } });

    const titleInput = screen.getByLabelText(/Название/i) as HTMLInputElement;
    expect(titleInput.value).toBe("edited");
    const usernameInput = screen.getByLabelText(/Username/i) as HTMLInputElement;
    expect(usernameInput.value).toBe("editeduser");
  });

  it("disables telegram_id input in edit mode", () => {
    const channel = makeChannel({ id: 5, title: "edited" });
    render(ChannelForm, { props: { channel, onSaved: vi.fn(), onCancel: vi.fn() } });

    const tgInput = screen.getByLabelText(/Telegram ID/i) as HTMLInputElement;
    expect(tgInput.disabled).toBe(true);
  });

  it("shows edit heading in edit mode", () => {
    const channel = makeChannel({ id: 5, title: "edited" });
    render(ChannelForm, { props: { channel, onSaved: vi.fn(), onCancel: vi.fn() } });
    expect(screen.getByText("Редактировать канал")).toBeTruthy();
  });

  it("calls PATCH on submit in edit mode", async () => {
    const channel = makeChannel({ id: 7, title: "old", username: "olduser" });
    const updated = makeChannel({ id: 7, title: "new", username: "newuser" });
    mockUpdateChannel.mockResolvedValue(updated);
    const onSaved = vi.fn();

    render(ChannelForm, { props: { channel, onSaved, onCancel: vi.fn() } });

    const titleInput = screen.getByLabelText(/Название/i) as HTMLInputElement;
    await fireEvent.input(titleInput, { target: { value: "new" } });
    const usernameInput = screen.getByLabelText(/Username/i) as HTMLInputElement;
    await fireEvent.input(usernameInput, { target: { value: "newuser" } });

    const form = screen.getByRole("button", { name: "Сохранить" }).closest("form");
    if (!form) throw new Error("form not found");
    await fireEvent.submit(form);

    await waitFor(() => {
      expect(mockUpdateChannel).toHaveBeenCalledWith(7, {
        title: "new",
        username: "newuser",
      });
    });
    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(updated);
    });
  });
});
