import { Lock, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { TicketDetail, TicketMessage } from "@/lib/types";
import { cn, formatDateTime, initials, timeAgo } from "@/lib/utils";

function Avatar({ name, staff }: { name: string; staff: boolean }) {
  return (
    <span
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
        staff ? "bg-brand-100 text-brand-700" : "bg-slate-200 text-slate-700",
      )}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

function Bubble({
  name,
  role,
  createdAt,
  body,
  internal,
  aiAssisted,
}: {
  name: string;
  role: string;
  createdAt: string;
  body: string;
  internal?: boolean;
  aiAssisted?: boolean;
}) {
  const staff = role !== "CUSTOMER";
  return (
    <li className="flex gap-3">
      <Avatar name={name} staff={staff} />
      <div
        className={cn(
          "min-w-0 flex-1 rounded-lg border px-4 py-3",
          internal ? "border-amber-200 bg-amber-50/70" : staff ? "border-brand-100 bg-brand-50/40" : "border-slate-200 bg-white",
        )}
      >
        <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <span className="font-semibold text-slate-900">{name}</span>
          <span className="text-slate-500">{staff ? "Support" : "Customer"}</span>
          {internal && (
            <Badge className="bg-amber-100 text-amber-800 ring-amber-600/20">
              <Lock className="size-3" aria-hidden /> Internal note
            </Badge>
          )}
          {aiAssisted && (
            <Badge className="bg-violet-50 text-violet-700 ring-violet-600/20" title="Drafted with AI and approved by an agent">
              <Sparkles className="size-3" aria-hidden /> AI-assisted
            </Badge>
          )}
          <time className="ml-auto text-slate-400" dateTime={createdAt} title={formatDateTime(createdAt)}>
            {timeAgo(createdAt)}
          </time>
        </div>
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-700">{body}</p>
      </div>
    </li>
  );
}

export function Conversation({ ticket, messages }: { ticket: TicketDetail; messages: TicketMessage[] }) {
  return (
    <ol className="space-y-4" aria-label="Conversation">
      <Bubble name={ticket.customer.name} role="CUSTOMER" createdAt={ticket.created_at} body={ticket.description} />
      {messages.map((m) => (
        <Bubble
          key={m.id}
          name={m.author.name}
          role={m.author.role}
          createdAt={m.created_at}
          body={m.body}
          internal={m.is_internal}
          aiAssisted={m.is_ai_assisted}
        />
      ))}
    </ol>
  );
}
