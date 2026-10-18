import { useActivities } from "@/api/tickets";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import type { TicketActivity } from "@/lib/types";
import { formatDateTime, timeAgo } from "@/lib/utils";

function describe(a: TicketActivity) {
  const label = (v: string) => STATUS_LABEL[v as keyof typeof STATUS_LABEL] ?? PRIORITY_LABEL[v as keyof typeof PRIORITY_LABEL] ?? v;
  switch (a.action) {
    case "created":
      return "created the ticket";
    case "status_changed":
      return <>changed status from <b>{label(a.from_value)}</b> to <b>{label(a.to_value)}</b></>;
    case "priority_changed":
      return <>changed priority from <b>{label(a.from_value)}</b> to <b>{label(a.to_value)}</b></>;
    case "category_changed":
      return <>changed category to <b>{a.to_value || "none"}</b></>;
    case "assigned":
      return <>assigned the ticket to <b>{a.to_value}</b></>;
    case "replied":
      return "replied";
    case "note_added":
      return "added an internal note";
    case "sla_changed":
      return "changed the SLA deadline";
    case "ai_classified":
      return <>AI classification suggested <b>{a.to_value}</b></>;
    case "ai_summarized":
      return "regenerated the AI summary";
    case "ai_reply_published":
      return "published an AI-assisted reply";
    default:
      return a.action_label;
  }
}

export function ActivityList({ ticketId }: { ticketId: number }) {
  const { data, isLoading, error, refetch } = useActivities(ticketId);
  if (isLoading) return <LoadingRows rows={3} />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (!data?.length) return <p className="p-4 text-sm text-slate-500">No activity yet.</p>;
  return (
    <ol className="relative space-y-4 border-l border-slate-200 pl-4" aria-label="Activity history">
      {data.map((a) => (
        <li key={a.id} className="relative text-sm">
          <span className="absolute -left-[21px] top-1.5 size-2.5 rounded-full border-2 border-white bg-slate-300" aria-hidden />
          <p className="text-slate-700">
            <span className="font-medium text-slate-900">{a.actor?.name ?? "System"}</span> {describe(a)}
          </p>
          <time className="text-xs text-slate-400" dateTime={a.created_at} title={formatDateTime(a.created_at)}>
            {timeAgo(a.created_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
