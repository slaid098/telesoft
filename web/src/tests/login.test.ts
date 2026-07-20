import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "../routes/login/+page.svelte";

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
  page: { url: new URL("http://localhost/login"), data: {} },
}));

beforeEach(() => {
  mockPost.mockReset();
  mockGoto.mockReset();
});

describe("Login page", () => {
  it("renders the form with username and password fields", () => {
    render(Login);
    expect(screen.getByLabelText(/Username/i)).toBeTruthy();
    expect(screen.getByLabelText(/Password/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Sign in/i })).toBeTruthy();
  });

  it("submits credentials and redirects on success", async () => {
    mockPost.mockResolvedValue({ status: "ok" });
    render(Login);

    const usernameInput = screen.getByLabelText(/Username/i);
    const passwordInput = screen.getByLabelText(/Password/i);
    await fireEvent.input(usernameInput, { target: { value: "admin" } });
    await fireEvent.input(passwordInput, { target: { value: "secret" } });
    await fireEvent.submit(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/api/auth/login", {
        username: "admin",
        password: "secret",
      });
    });
    await waitFor(() => {
      expect(mockGoto).toHaveBeenCalledWith("/channels", { replaceState: true });
    });
  });

  it("shows an error on 401 response", async () => {
    const { ApiError } = await import("../lib/api");
    mockPost.mockRejectedValue(new ApiError(401, null, "Invalid credentials"));
    render(Login);

    const usernameInput = screen.getByLabelText(/Username/i);
    const passwordInput = screen.getByLabelText(/Password/i);
    await fireEvent.input(usernameInput, { target: { value: "admin" } });
    await fireEvent.input(passwordInput, { target: { value: "wrong" } });
    await fireEvent.submit(screen.getByRole("button", { name: /Sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invalid credentials/i)).toBeTruthy();
    });
  });
});
