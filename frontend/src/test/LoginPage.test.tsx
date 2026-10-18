import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import LoginPage from "@/pages/LoginPage";

import { makeUser, renderWithProviders } from "./utils";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset();
  });

  it("validates the form before calling the API", async () => {
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login" });
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("logs in and redirects to the dashboard", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: makeUser("AGENT") });
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login", extraRoutes: <Route path="/" element={<p>dashboard home</p>} /> });

    await userEvent.type(screen.getByLabelText("Email"), "agent@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secret-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/auth/login/", { email: "agent@example.com", password: "secret-password" }));
    expect(await screen.findByText("dashboard home")).toBeInTheDocument();
  });

  it("shows the server's error message on failure", async () => {
    const { AxiosError, AxiosHeaders } = await import("axios");
    const config = { headers: new AxiosHeaders() };
    vi.mocked(api.post).mockImplementation(() =>
      Promise.reject(
        new AxiosError("401", undefined, config, null, { status: 401, data: { detail: "Invalid email or password." }, statusText: "", headers: {}, config } as never),
      ),
    );
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "agent@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Invalid email or password.")).toBeInTheDocument();
  });
});
