import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockGoto } = vi.hoisted(() => ({ mockGoto: vi.fn() }));

vi.mock("$app/environment", () => ({ browser: true }));

vi.mock("$app/navigation", () => ({ goto: mockGoto }));

import { API_BASE, ApiError, api } from "../lib/api";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

beforeEach(() => {
  mockGoto.mockReset();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  it("serializes query params into the URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await api.get("/api/channels", { active_only: true, missing: undefined, count: 5 });

    const calledUrl = fetchMock.mock.calls[0]?.[0];
    expect(calledUrl).toBe(`${API_BASE}/api/channels?active_only=true&count=5`);
  });

  it("throws ApiError on a non-ok response", async () => {
    globalThis.fetch = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse({ detail: "Not found" }, 404)),
      ) as unknown as typeof fetch;

    await expect(api.get("/api/channels/9999")).rejects.toMatchObject({
      status: 404,
      message: "Not found",
    });
    await expect(api.get("/api/channels/9999")).rejects.toBeInstanceOf(ApiError);
  });
});
