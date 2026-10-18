import { Check, CornerDownLeft, RefreshCw, ShieldAlert, Sparkles, Trash2, Wand2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  useClassify,
  useDiscardDraft,
  useDrafts,
  usePublishDraft,
  useSuggestReply,
  useSummarize,
  useUpdateTicket,
} from "@/api/tickets";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/api";
import type { ReplyDraft, TicketDetail } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

import { PriorityBadge } from "./badges";

function AIHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {action}
    </div>
  );
}

function Classification({ ticket, onUseResponse }: { ticket: TicketDetail; onUseResponse: (text: string) => void }) {
  const insight = ticket.ai_insight;
  const classify = useClassify(ticket.id);
  const update = useUpdateTicket(ticket.id);
  const status = insight?.classification_status;

  async function run() {
    try {
      await classify.mutateAsync(undefined);
      toast.success("AI analysis updated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function apply() {
    if (!insight) return;
    try {
      await update.mutateAsync({
        ...(insight.suggested_priority ? { priority: insight.suggested_priority } : {}),
        ...(insight.suggested_category ? { category_id: insight.suggested_category.id } : {}),
      });
      toast.success("Suggestions applied to the ticket.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  const rerun = (
    <Button variant="ghost" size="sm" onClick={run} loading={classify.isPending} disabled={!ticket.permissions.can_use_ai}>
      {!classify.isPending && <RefreshCw />} {insight && status !== "pending" ? "Re-run" : "Run"}
    </Button>
  );

  if (!insight || (!status && !insight.summary)) {
    return (
      <div>
        <AIHeader title="Triage suggestion" action={rerun} />
        <p className="text-sm text-slate-500">No AI analysis yet for this ticket.</p>
      </div>
    );
  }
  if (status === "pending") {
    return (
      <div aria-live="polite">
        <AIHeader title="Triage suggestion" />
        <p className="mb-2 flex items-center gap-2 text-sm text-slate-500">
          <Sparkles className="size-4 animate-pulse text-violet-500" /> Analysing ticket…
        </p>
        <Skeleton className="h-4 w-3/4" />
      </div>
    );
  }
  if (status === "failed" || status === "unavailable") {
    return (
      <div>
        <AIHeader title="Triage suggestion" action={status === "failed" ? rerun : undefined} />
        <Alert variant={status === "unavailable" ? "info" : "warning"} title={status === "unavailable" ? "AI is not configured" : "AI analysis failed"}>
          {insight.error_message || "The AI assistant is temporarily unavailable."} You can keep working on the ticket normally.
        </Alert>
      </div>
    );
  }

  const differs =
    (insight.suggested_priority && insight.suggested_priority !== ticket.priority) ||
    (insight.suggested_category && insight.suggested_category.id !== ticket.category?.id);

  return (
    <div>
      <AIHeader title="Triage suggestion" action={rerun} />
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-slate-500">Category</dt>
          <dd className="font-medium text-slate-900">{insight.suggested_category?.name ?? "No match"}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Priority</dt>
          <dd>{insight.suggested_priority ? <PriorityBadge priority={insight.suggested_priority} /> : "—"}</dd>
        </div>
      </dl>
      {insight.classification_reason && <p className="mt-2 text-xs text-slate-500">{insight.classification_reason}</p>}
      {insight.needs_human_review && (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-amber-700">
          <ShieldAlert className="size-3.5" /> Needs human review
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {differs && ticket.permissions.can_edit && (
          <Button size="sm" variant="outline" onClick={apply} loading={update.isPending}>
            {!update.isPending && <Check />} Apply suggestions
          </Button>
        )}
        {insight.suggested_first_response && ticket.permissions.can_reply && (
          <Button size="sm" variant="outline" onClick={() => onUseResponse(insight.suggested_first_response)}>
            <CornerDownLeft /> Use suggested first reply
          </Button>
        )}
      </div>
    </div>
  );
}

function Summary({ ticket }: { ticket: TicketDetail }) {
  const insight = ticket.ai_insight;
  const summarize = useSummarize(ticket.id);
  async function run() {
    try {
      await summarize.mutateAsync(undefined);
      toast.success("Summary regenerated.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }
  return (
    <div>
      <AIHeader
        title="Summary"
        action={
          <Button variant="ghost" size="sm" onClick={run} loading={summarize.isPending}>
            {!summarize.isPending && <RefreshCw />} {insight?.summary ? "Regenerate" : "Generate"}
          </Button>
        }
      />
      {summarize.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-5/6" />
        </div>
      ) : insight?.summary ? (
        <>
          <p className="text-sm leading-relaxed text-slate-700">{insight.summary}</p>
          <p className="mt-1.5 text-xs text-slate-400">
            Updated {timeAgo(insight.summary_updated_at)}
            {insight.summary_outdated && <span className="ml-1 font-medium text-amber-700">· New messages since then</span>}
          </p>
        </>
      ) : (
        <p className="text-sm text-slate-500">No summary yet.</p>
      )}
      {(insight?.summary_status === "failed" || insight?.summary_status === "unavailable") && !summarize.isPending && (
        <Alert variant="warning" className="mt-2">{insight.error_message}</Alert>
      )}
    </div>
  );
}

function DraftEditor({ ticketId, draft }: { ticketId: number; draft: ReplyDraft }) {
  const [body, setBody] = useState(draft.body);
  const [confirm, setConfirm] = useState(false);
  const publish = usePublishDraft(ticketId);
  const discard = useDiscardDraft(ticketId);

  useEffect(() => setBody(draft.body), [draft.body]);

  async function doPublish() {
    try {
      await publish.mutateAsync({ draftId: draft.id, body });
      setConfirm(false);
      toast.success("Reply sent to the customer.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <div className="rounded-lg border border-dashed border-violet-300 bg-violet-50/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <Badge className="bg-violet-100 text-violet-800 ring-violet-600/20">
          <Sparkles className="size-3" /> AI draft · not sent
        </Badge>
        <span className="text-xs text-slate-400">{timeAgo(draft.created_at)}</span>
      </div>
      <label htmlFor={`draft-${draft.id}`} className="sr-only">Edit AI draft</label>
      <Textarea id={`draft-${draft.id}`} value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[160px] bg-white" maxLength={5000} />
      {draft.referenced_articles.length > 0 && (
        <div className="mt-2 text-xs text-slate-500">
          <span className="font-medium">Based on:</span>{" "}
          {draft.referenced_articles.map((a, i) => (
            <span key={a.id}>
              {i > 0 && ", "}
              <Link to={`/kb/${a.id}`} className="text-brand-700 hover:underline">{a.title}</Link>
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => discard.mutate(draft.id, { onError: (e) => toast.error(getErrorMessage(e)) })} loading={discard.isPending}>
          {!discard.isPending && <Trash2 />} Discard
        </Button>
        <Button size="sm" onClick={() => setConfirm(true)} disabled={!body.trim()}>
          <Check /> Approve & send
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Send this reply to the customer?"
        description="The customer will see this message. It will be marked as AI-assisted."
        confirmLabel="Send reply"
        loading={publish.isPending}
        onConfirm={doPublish}
      />
    </div>
  );
}

function SuggestedReply({ ticket }: { ticket: TicketDetail }) {
  const drafts = useDrafts(ticket.id, ticket.permissions.can_use_ai);
  const suggest = useSuggestReply(ticket.id);
  const open = drafts.data?.filter((d) => d.status === "draft") ?? [];

  async function run() {
    try {
      await suggest.mutateAsync(undefined);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <div>
      <AIHeader title="Suggested reply" />
      <div className="space-y-3">
        {open.map((d) => (
          <DraftEditor key={d.id} ticketId={ticket.id} draft={d} />
        ))}
        {suggest.isPending && (
          <div className="space-y-2 rounded-lg border border-dashed border-violet-200 p-3" aria-live="polite">
            <p className="flex items-center gap-2 text-xs text-violet-700"><Sparkles className="size-3.5 animate-pulse" /> Drafting with knowledge-base context…</p>
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-4/6" />
          </div>
        )}
        {ticket.permissions.can_reply ? (
          <Button variant="ai" size="sm" className="w-full" onClick={run} disabled={suggest.isPending}>
            <Wand2 /> {open.length ? "Generate another draft" : "Draft a reply with AI"}
          </Button>
        ) : (
          <p className="text-sm text-slate-500">Closed tickets can't receive replies.</p>
        )}
        <p className="text-xs text-slate-400">Drafts stay private until you approve them.</p>
      </div>
    </div>
  );
}

export function AIPanel({ ticket, onUseResponse }: { ticket: TicketDetail; onUseResponse: (text: string) => void }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 bg-gradient-to-r from-violet-50 to-brand-50">
        <Sparkles className="size-4 text-violet-600" />
        <CardTitle>AI assistant</CardTitle>
        {ticket.ai_insight?.model_name && (
          <span className="ml-auto truncate text-[11px] text-slate-400">{ticket.ai_insight.model_name}</span>
        )}
      </CardHeader>
      <CardContent className="space-y-5 divide-y divide-slate-100 [&>*:not(:first-child)]:pt-5">
        <Summary ticket={ticket} />
        <Classification ticket={ticket} onUseResponse={onUseResponse} />
        <SuggestedReply ticket={ticket} />
      </CardContent>
    </Card>
  );
}

