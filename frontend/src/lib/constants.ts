import type { SLAStatus, TicketPriority, TicketStatus } from "./types";

export const STATUS_OPTIONS: { value: TicketStatus; label: string }[] = [
  { value: "OPEN", label: "Open" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "WAITING_FOR_CUSTOMER", label: "Waiting for Customer" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "CLOSED", label: "Closed" },
];

export const PRIORITY_OPTIONS: { value: TicketPriority; label: string }[] = [
  { value: "LOW", label: "Low" },
  { value: "MEDIUM", label: "Medium" },
  { value: "HIGH", label: "High" },
  { value: "URGENT", label: "Urgent" },
];

export const STATUS_LABEL: Record<TicketStatus, string> = Object.fromEntries(
  STATUS_OPTIONS.map((o) => [o.value, o.label]),
) as Record<TicketStatus, string>;

export const PRIORITY_LABEL: Record<TicketPriority, string> = Object.fromEntries(
  PRIORITY_OPTIONS.map((o) => [o.value, o.label]),
) as Record<TicketPriority, string>;

export const STATUS_STYLE: Record<TicketStatus, string> = {
  OPEN: "bg-blue-50 text-blue-700 ring-blue-600/20",
  IN_PROGRESS: "bg-violet-50 text-violet-700 ring-violet-600/20",
  WAITING_FOR_CUSTOMER: "bg-amber-50 text-amber-800 ring-amber-600/20",
  RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  CLOSED: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export const PRIORITY_STYLE: Record<TicketPriority, string> = {
  LOW: "bg-slate-100 text-slate-600 ring-slate-500/20",
  MEDIUM: "bg-sky-50 text-sky-700 ring-sky-600/20",
  HIGH: "bg-orange-50 text-orange-700 ring-orange-600/20",
  URGENT: "bg-red-50 text-red-700 ring-red-600/25",
};

export const SLA_STYLE: Record<SLAStatus, { label: string; className: string }> = {
  none: { label: "No SLA", className: "bg-slate-100 text-slate-500 ring-slate-400/20" },
  on_track: { label: "On track", className: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
  at_risk: { label: "At risk", className: "bg-amber-50 text-amber-800 ring-amber-600/25" },
  breached: { label: "Breached", className: "bg-red-50 text-red-700 ring-red-600/25" },
  met: { label: "SLA met", className: "bg-emerald-50 text-emerald-700 ring-emerald-600/20" },
};

// Chart colours (blue-led palette, distinguishable for common colour-vision deficiencies).
export const CHART = {
  primary: "#2563eb",
  secondary: "#14b8a6",
  muted: "#94a3b8",
  danger: "#dc2626",
  warning: "#f59e0b",
  series: ["#2563eb", "#14b8a6", "#f59e0b", "#8b5cf6", "#ec4899", "#64748b"],
  priority: { LOW: "#94a3b8", MEDIUM: "#38bdf8", HIGH: "#f97316", URGENT: "#dc2626" } as Record<TicketPriority, string>,
};
