import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthProvider } from "@/context/AuthContext";
import type { User } from "@/lib/types";

export function makeUser(role: User["role"], extra: Partial<User> = {}): User {
  return {
    id: role === "ADMIN" ? 1 : role === "AGENT" ? 2 : 3,
    email: `${role.toLowerCase()}@example.com`,
    first_name: "Test",
    last_name: role.toLowerCase(),
    name: `Test ${role.toLowerCase()}`,
    role,
    team: null,
    date_joined: "2026-01-01T00:00:00Z",
    last_login: null,
    ...extra,
  };
}

/** Renders `ui` inside providers, with an optional logged-in user and extra routes. */
export function renderWithProviders(
  ui: ReactElement,
  { user = null, route = "/", path = "*", extraRoutes }: { user?: User | null; route?: string; path?: string; extraRoutes?: ReactElement } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  client.setQueryData(["me"], user);
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider>
          <Routes>
            <Route path={path} element={ui} />
            {extraRoutes}
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}
