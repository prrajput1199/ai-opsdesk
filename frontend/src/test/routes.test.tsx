import { screen } from "@testing-library/react";
import { Route } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProtectedRoute } from "@/components/layout/ProtectedRoute";

import { makeUser, renderWithProviders } from "./utils";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } };
});

function tree() {
  return (
    <>
      <Route path="/login" element={<p>login page</p>} />
      <Route path="/" element={<p>dashboard</p>} />
      <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
        <Route path="/admin/users" element={<p>users admin</p>} />
      </Route>
    </>
  );
}

describe("ProtectedRoute", () => {
  it("sends anonymous users to the login page", () => {
    renderWithProviders(<p>unused</p>, { route: "/admin/users", path: "/unused", extraRoutes: tree() });
    expect(screen.getByText("login page")).toBeInTheDocument();
  });

  it("redirects users without the required role to the dashboard", () => {
    renderWithProviders(<p>unused</p>, { user: makeUser("CUSTOMER"), route: "/admin/users", path: "/unused", extraRoutes: tree() });
    expect(screen.getByText("dashboard")).toBeInTheDocument();
    expect(screen.queryByText("users admin")).not.toBeInTheDocument();
  });

  it("lets admins through", () => {
    renderWithProviders(<p>unused</p>, { user: makeUser("ADMIN"), route: "/admin/users", path: "/unused", extraRoutes: tree() });
    expect(screen.getByText("users admin")).toBeInTheDocument();
  });
});
