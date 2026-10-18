import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

import { meKey, useMe } from "@/api/auth";
import { setSessionExpiredHandler } from "@/lib/api";
import type { Role, User } from "@/lib/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isError: boolean;
  refetch: () => void;
  hasRole: (...roles: Role[]) => boolean;
  isStaff: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useMe();

  useEffect(() => {
    // When the refresh token is gone/expired, forget the user and drop other cached data; route
    // guards then redirect to /login. (Not qc.clear(): the /auth/me query may still be in flight.)
    setSessionExpiredHandler(() => {
      qc.setQueryData(meKey, null);
      qc.removeQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] });
    });
  }, [qc]);

  const value = useMemo<AuthState>(() => {
    const user = me.data ?? null;
    return {
      user,
      isLoading: me.isLoading,
      isError: me.isError,
      refetch: () => void me.refetch(),
      hasRole: (...roles) => !!user && roles.includes(user.role),
      isStaff: !!user && (user.role === "ADMIN" || user.role === "AGENT"),
      isAdmin: user?.role === "ADMIN",
    };
  }, [me]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
