import { render, screen } from "@testing-library/svelte";
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
}));

vi.mock("$app/navigation", () => ({ goto: mockGoto }));

vi.mock("$app/state", () => {
  let current = new URL("http://localhost/channels");
  return {
    page: {
      get url() {
        return current;
      },
      data: { user: "admin" },
    },
    setPage(url: URL) {
      current = url;
    },
  };
});

import LayoutHarness from "./LayoutHarness.svelte";

beforeEach(() => {
  mockPost.mockReset();
  mockGoto.mockReset();
});

describe("Layout navigation", () => {
  it("renders the Channels nav item", () => {
    render(LayoutHarness, { props: { data: { user: "admin" } } });
    expect(screen.getAllByText("Channels").length).toBeGreaterThanOrEqual(1);
  });

  it("renders the logout button", () => {
    render(LayoutHarness, { props: { data: { user: "admin" } } });
    expect(screen.getByRole("button", { name: /Logout/i })).toBeTruthy();
  });

  it("shows the signed-in username", () => {
    render(LayoutHarness, { props: { data: { user: "admin" } } });
    expect(screen.getAllByText(/admin/u).length).toBeGreaterThan(0);
  });
});
