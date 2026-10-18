import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { GuestRoute, ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { FullPageSpinner } from "@/components/ui/states";

// Pages are code-split so the login screen doesn't download charts, etc.
const LoginPage = lazy(() => import("@/pages/LoginPage"));
const RegisterPage = lazy(() => import("@/pages/RegisterPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const TicketsPage = lazy(() => import("@/pages/tickets/TicketsPage"));
const CreateTicketPage = lazy(() => import("@/pages/tickets/CreateTicketPage"));
const TicketDetailPage = lazy(() => import("@/pages/tickets/TicketDetailPage"));
const KnowledgeBasePage = lazy(() => import("@/pages/kb/KnowledgeBasePage"));
const ArticlePage = lazy(() => import("@/pages/kb/ArticlePage"));
const ArticleEditorPage = lazy(() => import("@/pages/kb/ArticleEditorPage"));
const AskPage = lazy(() => import("@/pages/kb/AskPage"));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage"));
const UsersPage = lazy(() => import("@/pages/admin/UsersPage"));
const SettingsPage = lazy(() => import("@/pages/admin/SettingsPage"));
const AuditLogPage = lazy(() => import("@/pages/admin/AuditLogPage"));
const ProfilePage = lazy(() => import("@/pages/ProfilePage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

export default function App() {
  return (
    <Suspense fallback={<FullPageSpinner />}>
      <Routes>
        <Route element={<GuestRoute />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="tickets" element={<TicketsPage />} />
            <Route path="tickets/:id" element={<TicketDetailPage />} />
            <Route path="kb" element={<KnowledgeBasePage />} />
            <Route path="kb/ask" element={<AskPage />} />
            <Route path="kb/:id" element={<ArticlePage />} />
            <Route path="profile" element={<ProfilePage />} />

            <Route element={<ProtectedRoute roles={["CUSTOMER"]} />}>
              <Route path="tickets/new" element={<CreateTicketPage />} />
            </Route>
            <Route element={<ProtectedRoute roles={["ADMIN", "AGENT"]} />}>
              <Route path="analytics" element={<AnalyticsPage />} />
            </Route>
            <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
              <Route path="kb/new" element={<ArticleEditorPage />} />
              <Route path="kb/:id/edit" element={<ArticleEditorPage />} />
              <Route path="admin/users" element={<UsersPage />} />
              <Route path="admin/settings" element={<SettingsPage />} />
              <Route path="admin/audit" element={<AuditLogPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
