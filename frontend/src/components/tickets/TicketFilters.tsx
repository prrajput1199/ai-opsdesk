import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { useAgents, useCategories, type TicketQuery } from "@/api/tickets";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { PRIORITY_OPTIONS, STATUS_OPTIONS } from "@/lib/constants";

export function TicketFilters({
  value,
  onChange,
  isStaff,
}: {
  value: TicketQuery;
  onChange: (next: TicketQuery) => void;
  isStaff: boolean;
}) {
  const categories = useCategories();
  const agents = useAgents(isStaff);
  const [search, setSearch] = useState(value.search ?? "");

  // Debounce the search box so we don't query on every keystroke.
  useEffect(() => {
    const id = setTimeout(() => {
      if ((value.search ?? "") !== search) onChange({ ...value, search, page: 1 });
    }, 350);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const set = (patch: Partial<TicketQuery>) => onChange({ ...value, ...patch, page: 1 });
  const active =
    !!value.search || !!value.status?.length || !!value.priority?.length || !!value.category ||
    !!value.assigned_agent || !!value.created_after || !!value.created_before || !!value.sla;

  return (
    <div className="space-y-3 border-b border-slate-100 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="relative sm:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <Input
            aria-label="Search by ticket number or title"
            placeholder="Search by number (OPS-000012) or title…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select aria-label="Status" value={value.status?.[0] ?? ""} onChange={(e) => set({ status: e.target.value ? [e.target.value] : [] })}>
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
        <Select aria-label="Priority" value={value.priority?.[0] ?? ""} onChange={(e) => set({ priority: e.target.value ? [e.target.value] : [] })}>
          <option value="">All priorities</option>
          {PRIORITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Select aria-label="Category" value={value.category ?? ""} onChange={(e) => set({ category: e.target.value })}>
          <option value="">All categories</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </Select>
        {isStaff && (
          <Select aria-label="Assigned agent" value={value.assigned_agent ?? ""} onChange={(e) => set({ assigned_agent: e.target.value })}>
            <option value="">Any agent</option>
            <option value="me">Assigned to me</option>
            <option value="unassigned">Unassigned</option>
            {agents.data?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </Select>
        )}
        {isStaff && (
          <Select aria-label="SLA" value={value.sla ?? ""} onChange={(e) => set({ sla: e.target.value })}>
            <option value="">Any SLA state</option>
            <option value="overdue">Overdue now</option>
            <option value="breached">Breached (incl. resolved)</option>
          </Select>
        )}
        <Input type="date" aria-label="Created from" value={value.created_after ?? ""} onChange={(e) => set({ created_after: e.target.value })} />
        <Input type="date" aria-label="Created until" value={value.created_before ?? ""} onChange={(e) => set({ created_before: e.target.value })} />
        <Select aria-label="Sort by" value={value.ordering ?? "-created_at"} onChange={(e) => set({ ordering: e.target.value })}>
          <option value="-created_at">Newest first</option>
          <option value="created_at">Oldest first</option>
          <option value="-updated_at">Recently updated</option>
          <option value="-priority_rank">Highest priority</option>
          <option value="sla_due_at">SLA deadline (soonest)</option>
        </Select>
      </div>
      {active && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setSearch("");
            onChange({ page: 1, ordering: value.ordering });
          }}
        >
          <X /> Clear filters
        </Button>
      )}
    </div>
  );
}
