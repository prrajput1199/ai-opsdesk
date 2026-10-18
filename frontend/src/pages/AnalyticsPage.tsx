import { AlertTriangle, CheckCircle2, Clock, Inbox, Timer, TrendingUp } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useAgentWorkload, useCategoryBreakdown, useOverview, useResolutionTime, useSLAReport, useTrends } from "@/api/analytics";
import { CategoryChart, PriorityChart, ResolutionChart, TrendChart, WorkloadChart } from "@/components/analytics/Charts";
import { DateRangePicker, type Range } from "@/components/analytics/DateRangePicker";
import { PriorityBadge } from "@/components/tickets/badges";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAuth } from "@/context/AuthContext";
import { formatHours, isoDaysAgo } from "@/lib/utils";

function ChartCard({ title, description, query, children }: {
  title: string;
  description?: string;
  query: { isLoading: boolean; error: unknown; refetch: () => unknown };
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        {query.isLoading ? <LoadingRows rows={4} /> : query.error ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : children}
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const { isAdmin } = useAuth();
  const [range, setRange] = useState<Range>({ date_from: isoDaysAgo(29), date_to: isoDaysAgo(0) });
  const overview = useOverview(range);
  const trends = useTrends(range);
  const breakdown = useCategoryBreakdown(range);
  const resolution = useResolutionTime(range);
  const sla = useSLAReport(range);
  const workload = useAgentWorkload(range, isAdmin);
  const o = overview.data;

  return (
    <>
      <PageHeader
        title={isAdmin ? "Analytics & agent workload" : "Analytics"}
        description={isAdmin ? "Organisation-wide metrics from live ticket data." : "Metrics for the tickets you and your team can access."}
        actions={<DateRangePicker value={range} onChange={setRange} />}
      />

      {overview.error ? (
        <Card className="mb-6"><ErrorState error={overview.error} onRetry={() => overview.refetch()} /></Card>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Tickets created" value={o?.total_tickets ?? 0} icon={<Inbox />} loading={overview.isLoading} />
          <StatCard label="Open now" value={o?.active_tickets ?? 0} hint={`${o?.unassigned_active_tickets ?? 0} unassigned`} icon={<Clock />} loading={overview.isLoading} />
          <StatCard label="Resolved in range" value={o?.resolved_in_range ?? 0} icon={<CheckCircle2 />} tone="success" loading={overview.isLoading} />
          <StatCard label="Avg. resolution" value={formatHours(o?.avg_resolution_hours)} icon={<Timer />} loading={overview.isLoading} />
          <StatCard label="Avg. first response" value={formatHours(o?.avg_first_response_hours)} icon={<TrendingUp />} loading={overview.isLoading} />
          <StatCard label="SLA compliance" value={o?.sla_compliance_rate == null ? "—" : `${o.sla_compliance_rate}%`} hint={`${o?.overdue_tickets ?? 0} overdue now`} icon={<AlertTriangle />} tone={(o?.overdue_tickets ?? 0) > 0 ? "danger" : "success"} loading={overview.isLoading} />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ChartCard title="Tickets over time" description="Created vs. resolved per day" query={trends}>
            {trends.data && <TrendChart data={trends.data.series} height={280} />}
          </ChartCard>
        </div>
        <ChartCard title="By priority" description="Tickets created in range" query={breakdown}>
          {breakdown.data && <PriorityChart data={breakdown.data.priorities} height={280} />}
        </ChartCard>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="By category" description="Total vs. still active" query={breakdown}>
          {breakdown.data && (breakdown.data.categories.length ? <CategoryChart data={breakdown.data.categories} /> : <EmptyState title="No tickets in this range" />)}
        </ChartCard>
        <ChartCard title="Resolution time" description={resolution.data?.definition} query={resolution}>
          {resolution.data && (
            <>
              <ResolutionChart data={resolution.data.distribution} />
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {resolution.data.by_priority.map((p) => (
                  <div key={p.priority} className="rounded-lg bg-slate-50 p-2.5 text-center">
                    <PriorityBadge priority={p.priority} />
                    <p className="mt-1 text-sm font-semibold tabular-nums text-slate-900">{formatHours(p.avg_resolution_hours)}</p>
                    <p className="text-[11px] text-slate-500">{p.resolved_count} resolved</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </ChartCard>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>SLA status</CardTitle>
          <CardDescription>Active tickets right now; met/breached counts use resolution dates in the selected range</CardDescription>
        </CardHeader>
        {sla.isLoading ? <LoadingRows rows={3} /> : sla.error ? <ErrorState error={sla.error} onRetry={() => sla.refetch()} /> : sla.data && (
          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                { label: "Overdue", value: sla.data.overdue, cls: "text-red-600" },
                { label: "At risk", value: sla.data.at_risk, cls: "text-amber-600" },
                { label: "On track", value: sla.data.on_track, cls: "text-emerald-600" },
                { label: "Resolved within SLA", value: sla.data.resolved_within_sla, cls: "text-slate-900" },
                { label: "Resolved late", value: sla.data.resolved_breached, cls: "text-slate-900" },
              ].map((s) => (
                <div key={s.label} className="rounded-lg border border-slate-100 p-3">
                  <p className="text-xs text-slate-500">{s.label}</p>
                  <p className={`text-xl font-semibold tabular-nums ${s.cls}`}>{s.value}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500">
              Targets: {sla.data.policies.map((p) => `${p.label} ${p.resolution_hours}h`).join(" · ")}
              {isAdmin && <> — <Link to="/admin/settings" className="text-brand-700 hover:underline">edit</Link></>}
            </p>
            {sla.data.overdue_tickets.length > 0 && (
              <Table>
                <THead><TR><TH>Ticket</TH><TH>Priority</TH><TH>Assignee</TH><TH className="text-right">Overdue by</TH></TR></THead>
                <TBody>
                  {sla.data.overdue_tickets.map((t) => (
                    <TR key={t.id} className="hover:bg-slate-50">
                      <TD><Link to={`/tickets/${t.id}`} className="font-medium text-slate-900 hover:text-brand-700">{t.title}</Link><span className="block font-mono text-xs text-slate-500">{t.number}</span></TD>
                      <TD><PriorityBadge priority={t.priority} /></TD>
                      <TD>{t.assigned_agent ?? <span className="text-slate-400">Unassigned</span>}</TD>
                      <TD className="text-right font-medium text-red-600">{formatHours(t.hours_overdue)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        )}
      </Card>

      {isAdmin && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Agent workload</CardTitle>
            <CardDescription>Active tickets per agent now; resolved counts and averages for the selected range</CardDescription>
          </CardHeader>
          {workload.isLoading ? <LoadingRows /> : workload.error ? <ErrorState error={workload.error} onRetry={() => workload.refetch()} /> : !workload.data?.agents.length ? (
            <EmptyState title="No active agents" description="Create agent accounts under Users & agents." />
          ) : (
            <>
              <CardContent><WorkloadChart data={workload.data.agents} /></CardContent>
              <Table>
                <THead>
                  <TR><TH>Agent</TH><TH>Team</TH><TH className="text-right">Active</TH><TH className="text-right">Urgent</TH><TH className="text-right">Overdue</TH><TH className="text-right">Resolved</TH><TH className="text-right">Avg. resolution</TH></TR>
                </THead>
                <TBody>
                  {workload.data.agents.map((a) => (
                    <TR key={a.id}>
                      <TD><span className="font-medium text-slate-900">{a.name}</span><span className="block text-xs text-slate-500">{a.email}</span></TD>
                      <TD>{a.team ?? "—"}</TD>
                      <TD className="text-right tabular-nums">{a.active}</TD>
                      <TD className="text-right tabular-nums">{a.urgent}</TD>
                      <TD className={`text-right tabular-nums ${a.overdue ? "font-medium text-red-600" : ""}`}>{a.overdue}</TD>
                      <TD className="text-right tabular-nums">{a.resolved_in_range}</TD>
                      <TD className="text-right tabular-nums">{formatHours(a.avg_resolution_hours)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </>
          )}
        </Card>
      )}
    </>
  );
}
