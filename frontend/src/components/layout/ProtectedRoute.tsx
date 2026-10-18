import { Navigate, Outlet, useLocation } from "react-router-dom";

import { ErrorState, FullPageSpinner } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/lib/types";

/** Requires a logged-in user; optionally one of `roles`. The API enforces the same rules. */
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, isLoading, isError, refetch } = useAuth();
  const location = useLocation();

  if (isLoading) return <FullPageSpinner />;
  if (isError) return <ErrorState error={new Error()} title="Couldn't reach the server" onRetry={refetch} className="min-h-screen" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}

/** For /login and /register: logged-in users go to the dashboard. */
export function GuestRoute() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <FullPageSpinner />;
  if (user) return <Navigate to="/" replace />;
  return <Outlet />;
}
