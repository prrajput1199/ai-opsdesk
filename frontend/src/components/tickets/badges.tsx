import { AlertTriangle, CheckCircle2, Clock, Flame } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { PRIORITY_LABEL, PRIORITY_STYLE, SLA_STYLE, STATUS_LABEL, STATUS_STYLE } from "@/lib/constants";
import type { SLAStatus, TicketPriority, TicketStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, className }: { status: TicketStatus; className?: string }) {
  return <Badge className={cn(STATUS_STYLE[status], className)}>{STATUS_LABEL[status]}</Badge>;
}

export function PriorityBadge({ priority, className }: { priority: TicketPriority; className?: string }) {
  return (
    <Badge className={cn(PRIORITY_STYLE[priority], className)}>
      {priority === "URGENT" && <Flame className="size-3" aria-hidden />}
      {PRIORITY_LABEL[priority]}
    </Badge>
  );
}

export function SLABadge({ status, className }: { status: SLAStatus; className?: string }) {
  const { label, className: style } = SLA_STYLE[status];
  const Icon = status === "breached" ? AlertTriangle : status === "at_risk" ? Clock : status === "none" ? null : CheckCircle2;
  return (
    <Badge className={cn(style, className)} title={`SLA: ${label}`}>
      {Icon && <Icon className="size-3" aria-hidden />}
      {label}
    </Badge>
  );
}
