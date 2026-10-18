import { UserPlus } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { useAgents, useAssign, useCategories, useTransition, useUpdateTicket } from "@/api/tickets";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api";
import { PRIORITY_OPTIONS, STATUS_LABEL } from "@/lib/constants";
import type { TicketDetail, TicketPriority, TicketStatus } from "@/lib/types";
import { formatDateTime, timeAgo } from "@/lib/utils";

import { PriorityBadge, SLABadge, StatusBadge } from "./badges";

const TRANSITION_LABEL: Partial<Record<TicketStatus, string>> = {
  IN_PROGRESS: "Start progress",
  WAITING_FOR_CUSTOMER: "Wait for customer",
  RESOLVED: "Mark resolved",
  CLOSED: "Close ticket",
  OPEN: "Reopen",
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{children}</dd>
    </div>
  );
}

export function TicketControls({ ticket }: { ticket: TicketDetail }) {
  const { user, isAdmin, isStaff } = useAuth();
  const transition = useTransition(ticket.id);
  const update = useUpdateTicket(ticket.id);
  const assign = useAssign(ticket.id);
  const categories = useCategories();
  const agents = useAgents(isAdmin);

  const run = async (fn: () => Promise<unknown>, success: string) => {
    try {
      await fn();
      toast.success(success);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {ticket.allowed_transitions.length > 0 && (
          <div className="flex flex-wrap gap-2" aria-label="Change status">
            {ticket.allowed_transitions.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={s === "RESOLVED" ? "default" : s === "CLOSED" ? "outline" : "secondary"}
                loading={transition.isPending && transition.variables === s}
                disabled={transition.isPending}
                onClick={() => run(() => transition.mutateAsync(s), `Status changed to ${STATUS_LABEL[s]}.`)}
              >
                {user?.role === "CUSTOMER" && s === "CLOSED" ? "Close ticket" : TRANSITION_LABEL[s] ?? STATUS_LABEL[s]}
              </Button>
            ))}
          </div>
        )}

        {ticket.permissions.can_edit && (
          <div className="grid gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="priority">Priority</Label>
              <Select
                id="priority"
                value={ticket.priority}
                disabled={update.isPending}
                onChange={(e) => run(() => update.mutateAsync({ priority: e.target.value as TicketPriority }), "Priority updated. SLA deadline recalculated.")}
              >
                {PRIORITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="category">Category</Label>
              <Select
                id="category"
                value={ticket.category?.id ?? ""}
                disabled={update.isPending}
                onChange={(e) => run(() => update.mutateAsync({ category_id: e.target.value ? Number(e.target.value) : null }), "Category updated.")}
              >
                <option value="">Uncategorised</option>
                {categories.data?.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </Select>
            </div>
            {isAdmin && ticket.status !== "CLOSED" && (
              <div className="space-y-1.5">
                <Label htmlFor="assignee">Assignee</Label>
                <Select
                  id="assignee"
                  value={ticket.assigned_agent?.id ?? ""}
                  disabled={assign.isPending}
                  onChange={(e) => run(() => assign.mutateAsync(e.target.value ? Number(e.target.value) : null), "Assignment updated.")}
                >
                  <option value="">Unassigned</option>
                  {agents.data?.map((a) => (
                    <option key={a.id} value={a.id}>{a.name} ({a.role === "ADMIN" ? "Admin" : "Agent"})</option>
                  ))}
                </Select>
              </div>
            )}
          </div>
        )}

        {!isAdmin && isStaff && ticket.permissions.can_assign && (
          <Button variant="outline" size="sm" className="w-full" loading={assign.isPending} onClick={() => run(() => assign.mutateAsync(user!.id), "Ticket assigned to you.")}>
            {!assign.isPending && <UserPlus />} Assign to me
          </Button>
        )}

        <dl className="divide-y divide-slate-100 border-t border-slate-100">
          <Row label="Status"><StatusBadge status={ticket.status} /></Row>
          {!ticket.permissions.can_edit && <Row label="Priority"><PriorityBadge priority={ticket.priority} /></Row>}
          {!ticket.permissions.can_edit && <Row label="Category">{ticket.category?.name ?? "—"}</Row>}
          {(!isAdmin || ticket.status === "CLOSED") && <Row label="Assignee">{ticket.assigned_agent?.name ?? "Unassigned"}</Row>}
          {isStaff && <Row label="Customer"><span className="block">{ticket.customer.name}</span><span className="block text-xs font-normal text-slate-500">{ticket.customer.email}</span></Row>}
          <Row label="SLA"><SLABadge status={ticket.sla_status} /></Row>
          <Row label="Due"><span title={formatDateTime(ticket.sla_due_at)}>{ticket.sla_due_at ? formatDateTime(ticket.sla_due_at) : "—"}</span></Row>
          <Row label="Created"><span title={formatDateTime(ticket.created_at)}>{timeAgo(ticket.created_at)}</span></Row>
          <Row label="First response">{ticket.first_response_at ? timeAgo(ticket.first_response_at) : "—"}</Row>
          {ticket.resolved_at && <Row label="Resolved">{formatDateTime(ticket.resolved_at)}</Row>}
          {ticket.closed_at && <Row label="Closed">{formatDateTime(ticket.closed_at)}</Row>}
        </dl>
      </CardContent>
    </Card>
  );
}
