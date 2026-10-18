import { MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";

import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { TicketListItem } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

import { PriorityBadge, SLABadge, StatusBadge } from "./badges";

export function TicketTable({ tickets, showCustomer }: { tickets: TicketListItem[]; showCustomer: boolean }) {
  return (
    <>
      {/* Mobile: cards */}
      <ul className="divide-y divide-slate-100 md:hidden">
        {tickets.map((t) => (
          <li key={t.id}>
            <Link to={`/tickets/${t.id}`} className="block space-y-2 p-4 hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none">
              <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
                <span className="font-mono">{t.number}</span>
                <span>{timeAgo(t.created_at)}</span>
              </div>
              <p className="font-medium text-slate-900">{t.title}</p>
              <div className="flex flex-wrap gap-1.5">
                <StatusBadge status={t.status} />
                <PriorityBadge priority={t.priority} />
                {t.status !== "CLOSED" && <SLABadge status={t.sla_status} />}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Desktop: table */}
      <div className="hidden md:block">
        <Table>
          <THead>
            <TR>
              <TH>Ticket</TH>
              <TH>Status</TH>
              <TH>Priority</TH>
              <TH>SLA</TH>
              <TH>Category</TH>
              {showCustomer && <TH>Customer</TH>}
              <TH>Assignee</TH>
              <TH className="text-right">Created</TH>
            </TR>
          </THead>
          <TBody>
            {tickets.map((t) => (
              <TR key={t.id} className="hover:bg-slate-50">
                <TD className="max-w-[340px]">
                  <Link to={`/tickets/${t.id}`} className="group block rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
                    <span className="block truncate font-medium text-slate-900 group-hover:text-brand-700">{t.title}</span>
                    <span className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                      <span className="font-mono">{t.number}</span>
                      {t.message_count > 0 && (
                        <span className="inline-flex items-center gap-0.5">
                          <MessageSquare className="size-3" aria-hidden /> {t.message_count}
                        </span>
                      )}
                    </span>
                  </Link>
                </TD>
                <TD><StatusBadge status={t.status} /></TD>
                <TD><PriorityBadge priority={t.priority} /></TD>
                <TD>{t.status === "CLOSED" && t.sla_status === "none" ? <span className="text-slate-400">—</span> : <SLABadge status={t.sla_status} />}</TD>
                <TD className="whitespace-nowrap">{t.category?.name ?? <span className="text-slate-400">—</span>}</TD>
                {showCustomer && <TD className="whitespace-nowrap">{t.customer.name}</TD>}
                <TD className="whitespace-nowrap">{t.assigned_agent?.name ?? <span className="text-slate-400">Unassigned</span>}</TD>
                <TD className="whitespace-nowrap text-right text-slate-500" title={t.created_at}>{timeAgo(t.created_at)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
    </>
  );
}
