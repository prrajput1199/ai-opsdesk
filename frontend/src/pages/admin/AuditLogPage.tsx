import { ScrollText, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { useAuditLogs } from "@/api/admin";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDateTime } from "@/lib/utils";

const ACTIONS: [string, string][] = [
  ["auth.login", "Logged in"], ["auth.login_failed", "Failed login"], ["auth.logout", "Logged out"], ["auth.register", "Registered"],
  ["auth.password_changed", "Changed password"], ["user.created", "Created user"], ["user.updated", "Updated user"],
  ["user.deactivated", "Deactivated user"], ["user.activated", "Activated user"], ["ticket.created", "Created ticket"],
  ["ticket.updated", "Updated ticket"], ["ticket.assigned", "Assigned ticket"], ["ticket.status_changed", "Changed ticket status"],
  ["ai.reply_published", "Published AI-assisted reply"], ["category.changed", "Changed category"], ["sla.changed", "Changed SLA policy"],
  ["team.changed", "Changed team"], ["kb.article_created", "Created article"], ["kb.article_updated", "Updated article"], ["kb.article_deleted", "Deleted article"],
];

function actionTone(action: string) {
  if (action === "auth.login_failed" || action === "user.deactivated" || action === "kb.article_deleted") return "bg-red-50 text-red-700 ring-red-600/20";
  if (action.startsWith("ai.")) return "bg-violet-50 text-violet-700 ring-violet-600/20";
  if (action.startsWith("auth.")) return "bg-slate-100 text-slate-700 ring-slate-500/20";
  return "bg-brand-50 text-brand-700 ring-brand-600/20";
}

export default function AuditLogPage() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const id = setTimeout(() => { setDebounced(search); setPage(1); }, 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data, isLoading, error, refetch } = useAuditLogs({ page, search: debounced, action, date_from: dateFrom, date_to: dateTo });

  return (
    <>
      <PageHeader title="Audit log" description="Security-relevant and business-critical actions. Entries are read-only." />
      <Card>
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <Input className="pl-9" placeholder="Search actor, description…" aria-label="Search audit log" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select aria-label="Action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
            <option value="">All actions</option>
            {ACTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
          <Input type="date" aria-label="From date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} />
          <Input type="date" aria-label="To date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} />
        </div>
        {isLoading ? <LoadingRows /> : error ? <ErrorState error={error} onRetry={() => refetch()} /> : !data?.results.length ? (
          <EmptyState icon={<ScrollText />} title="No audit entries match" />
        ) : (
          <>
            <Table>
              <THead><TR><TH>When</TH><TH>Actor</TH><TH>Action</TH><TH>Details</TH><TH>IP address</TH></TR></THead>
              <TBody>
                {data.results.map((e) => (
                  <TR key={e.id}>
                    <TD className="whitespace-nowrap text-slate-500">{formatDateTime(e.created_at)}</TD>
                    <TD className="whitespace-nowrap">{e.actor_email || <span className="text-slate-400">anonymous</span>}</TD>
                    <TD><Badge className={actionTone(e.action)}>{e.action_label}</Badge></TD>
                    <TD className="max-w-md">
                      <p className="truncate">{e.description}</p>
                      {e.target_type && <p className="text-xs text-slate-400">{e.target_type} #{e.target_id}</p>}
                    </TD>
                    <TD className="whitespace-nowrap font-mono text-xs text-slate-500">{e.ip_address ?? "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={20} count={data.count} onPageChange={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
