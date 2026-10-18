import { AlertTriangle, BookOpen, CheckCircle2, Clock, Flame, Inbox, PlusCircle, Timer, UserX } from "lucide-react";
import { Link } from "react-router-dom";

import { useOverview, useSLAReport, useTrends } from "@/api/analytics";
import { useTickets } from "@/api/tickets";
import { TrendChart } from "@/components/analytics/Charts";
import { PriorityBadge, StatusBadge } from "@/components/tickets/badges";
import { TicketTable } from "@/components/tickets/TicketTable";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";
import { formatHours, isoDaysAgo, timeAgo } from "@/lib/utils";

function CustomerDashboard() {
  const { user } = useAuth();
  const overview = useOverview();
  const recent = useTickets({ page_size: 5, ordering: "-updated_at" });
  const o = overview.data;

  return (
    <>
      <PageHeader
        title={`Hi ${user?.first_name || "there"} 👋`}
        description="Track your support requests and find answers."
        actions={
          <>
            <Button variant="outline" asChild><Link to="/kb/ask"><BookOpen /> Search help articles</Link></Button>
            <Button asChild><Link to="/tickets/new"><PlusCircle /> New ticket</Link></Button>
          </>
        }
      />
      {overview.isError ? (
        <Card className="mb-6"><ErrorState error={overview.error} onRetry={() => overview.refetch()} /></Card>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Open" value={o?.open_tickets ?? 0} icon={<Inbox />} loading={overview.isLoading} />
          <StatCard label="In progress / waiting on you" value={(o?.in_progress_tickets ?? 0) + (o?.waiting_for_customer_tickets ?? 0)} icon={<Clock />} tone="warning" loading={overview.isLoading} />
          <StatCard label="Resolved" value={o?.resolved_tickets ?? 0} icon={<CheckCircle2 />} tone="success" loading={overview.isLoading} />
          <StatCard label="All my tickets" value={o?.total_tickets ?? 0} icon={<Timer />} loading={overview.isLoading} />
        </div>
      )}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Your most recently updated tickets</CardDescription>
          </div>
          <Button variant="link" size="sm" asChild><Link to="/tickets">View all</Link></Button>
        </CardHeader>
        {recent.isLoading ? (
          <LoadingRows rows={3} />
        ) : recent.isError ? (
          <ErrorState error={recent.error} onRetry={() => recent.refetch()} />
        ) : !recent.data?.results.length ? (
          <EmptyState title="No tickets yet" description="When you contact support, your tickets will appear here."
            action={<Button asChild><Link to="/tickets/new">Create your first ticket</Link></Button>} />
        ) : (
          <TicketTable tickets={recent.data.results} showCustomer={false} />
        )}
      </Card>
    </>
  );
}

function StaffDashboard() {
  const { user, isAdmin } = useAuth();
  const overview = useOverview();
  const trends = useTrends({ date_from: isoDaysAgo(13), date_to: isoDaysAgo(0) });
  const sla = useSLAReport();
  const myQueue = useTickets({
    page_size: 6,
    assigned_agent: isAdmin ? "unassigned" : "me",
    status: ["OPEN", "IN_PROGRESS", "WAITING_FOR_CUSTOMER"],
    ordering: "sla_due_at",
  });
  const o = overview.data;

  return (
    <>
      <PageHeader
        title={`Good to see you, ${user?.first_name || ""}`.trim()}
        description={isAdmin ? "Organisation-wide view of your support operation." : "Your queue and your team's tickets at a glance."}
        actions={<Button asChild><Link to="/tickets"><Inbox /> Open ticket queue</Link></Button>}
      />
      {overview.isError ? (
        <Card className="mb-6"><ErrorState error={overview.error} onRetry={() => overview.refetch()} /></Card>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Active tickets" value={o?.active_tickets ?? 0} icon={<Inbox />} loading={overview.isLoading} />
          <StatCard label="Unassigned" value={o?.unassigned_active_tickets ?? 0} icon={<UserX />} tone="warning" loading={overview.isLoading} />
          <StatCard label="Urgent (active)" value={o?.urgent_active_tickets ?? 0} icon={<Flame />} tone="danger" loading={overview.isLoading} />
          <StatCard label="Overdue (SLA)" value={o?.overdue_tickets ?? 0} icon={<AlertTriangle />} tone="danger" loading={overview.isLoading} />
          <StatCard label="Avg. resolution" value={formatHours(o?.avg_resolution_hours)} hint={`${o?.resolved_in_range ?? 0} resolved tickets`} icon={<Timer />} loading={overview.isLoading} />
          <StatCard label="SLA compliance" value={o?.sla_compliance_rate == null ? "—" : `${o.sla_compliance_rate}%`} icon={<CheckCircle2 />} tone="success" loading={overview.isLoading} />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Ticket volume</CardTitle>
            <CardDescription>Created vs. resolved, last 14 days</CardDescription>
          </CardHeader>
          <CardContent>
            {trends.isLoading ? <LoadingRows rows={4} /> : trends.isError ? <ErrorState error={trends.error} onRetry={() => trends.refetch()} /> : <TrendChart data={trends.data!.series} />}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>Overdue tickets</CardTitle>
              <CardDescription>Past their SLA deadline</CardDescription>
            </div>
            <Button variant="link" size="sm" asChild><Link to="/tickets?sla=overdue">View all</Link></Button>
          </CardHeader>
          {sla.isLoading ? (
            <LoadingRows rows={4} />
          ) : sla.isError ? (
            <ErrorState error={sla.error} onRetry={() => sla.refetch()} />
          ) : !sla.data?.overdue_tickets.length ? (
            <EmptyState icon={<CheckCircle2 />} title="Nothing overdue" description="Every active ticket is within its SLA." />
          ) : (
            <ul className="divide-y divide-slate-100">
              {sla.data.overdue_tickets.slice(0, 6).map((t) => (
                <li key={t.id}>
                  <Link to={`/tickets/${t.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-900">{t.title}</p>
                      <p className="text-xs text-slate-500"><span className="font-mono">{t.number}</span> · {t.assigned_agent ?? "Unassigned"}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <PriorityBadge priority={t.priority} />
                      <span className="text-xs font-medium text-red-600">{formatHours(t.hours_overdue)} late</span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>{isAdmin ? "Unassigned queue" : "My active tickets"}</CardTitle>
            <CardDescription>Sorted by SLA deadline</CardDescription>
          </div>
          <Button variant="link" size="sm" asChild>
            <Link to={`/tickets?assigned_agent=${isAdmin ? "unassigned" : "me"}`}>View all</Link>
          </Button>
        </CardHeader>
        {myQueue.isLoading ? (
          <LoadingRows rows={3} />
        ) : myQueue.isError ? (
          <ErrorState error={myQueue.error} onRetry={() => myQueue.refetch()} />
        ) : !myQueue.data?.results.length ? (
          <EmptyState icon={<CheckCircle2 />} title={isAdmin ? "Every active ticket has an owner" : "Your queue is clear"} />
        ) : (
          <ul className="divide-y divide-slate-100">
            {myQueue.data.results.map((t) => (
              <li key={t.id}>
                <Link to={`/tickets/${t.id}`} className="flex flex-wrap items-center gap-3 px-5 py-3 hover:bg-slate-50">
                  <span className="font-mono text-xs text-slate-500">{t.number}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">{t.title}</span>
                  <StatusBadge status={t.status} />
                  <PriorityBadge priority={t.priority} />
                  <span className="w-24 text-right text-xs text-slate-500">{timeAgo(t.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

export default function DashboardPage() {
  const { isStaff } = useAuth();
  return isStaff ? <StaffDashboard /> : <CustomerDashboard />;
}
