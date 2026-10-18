import { ArrowLeft } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useComments, useTicket } from "@/api/tickets";
import { ActivityList } from "@/components/tickets/ActivityList";
import { AIPanel } from "@/components/tickets/AIPanel";
import { Conversation } from "@/components/tickets/Conversation";
import { RelatedArticles } from "@/components/tickets/RelatedArticles";
import { ReplyComposer } from "@/components/tickets/ReplyComposer";
import { TicketControls } from "@/components/tickets/TicketControls";
import { PriorityBadge, SLABadge, StatusBadge } from "@/components/tickets/badges";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/context/AuthContext";
import { formatDateTime } from "@/lib/utils";

import NotFoundPage from "../NotFoundPage";

export default function TicketDetailPage() {
  const id = Number(useParams().id);
  const { isStaff } = useAuth();
  const ticket = useTicket(id);
  const comments = useComments(id);
  const [prefill, setPrefill] = useState<string | null>(null);
  const clearPrefill = useCallback(() => setPrefill(null), []);

  if (!Number.isFinite(id)) return <NotFoundPage />;
  if (ticket.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-5 w-1/3" />
        <LoadingRows rows={4} />
      </div>
    );
  }
  if (ticket.error) {
    const status = (ticket.error as { response?: { status?: number } }).response?.status;
    if (status === 404) return <NotFoundPage />;
    return <Card><ErrorState error={ticket.error} onRetry={() => ticket.refetch()} /></Card>;
  }
  const t = ticket.data!;

  return (
    <>
      <Link to="/tickets" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" /> Back to tickets
      </Link>
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <span className="font-mono">{t.number}</span>
          <span aria-hidden>·</span>
          <span>Opened {formatDateTime(t.created_at)}</span>
        </div>
        <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">{t.title}</h1>
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusBadge status={t.status} />
          <PriorityBadge priority={t.priority} />
          {t.category && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{t.category.name}</span>}
          {t.status !== "CLOSED" && <SLABadge status={t.sla_status} />}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Tabs defaultValue="conversation">
            <TabsList>
              <TabsTrigger value="conversation">Conversation</TabsTrigger>
              <TabsTrigger value="activity">Activity</TabsTrigger>
            </TabsList>
            <TabsContent value="conversation" className="space-y-6">
              {comments.isLoading ? (
                <LoadingRows rows={3} />
              ) : comments.error ? (
                <Card><ErrorState error={comments.error} onRetry={() => comments.refetch()} /></Card>
              ) : (
                <Conversation ticket={t} messages={comments.data ?? []} />
              )}
              {t.permissions.can_reply ? (
                <ReplyComposer ticketId={t.id} canAddInternalNote={t.permissions.can_add_internal_note} prefill={prefill} onPrefillConsumed={clearPrefill} />
              ) : (
                <Alert variant="info" title="This ticket is closed">
                  {isStaff ? "Closed tickets can't receive new messages." : "Need more help? Please open a new ticket."}
                </Alert>
              )}
            </TabsContent>
            <TabsContent value="activity">
              <Card>
                <CardHeader><CardTitle>Activity history</CardTitle></CardHeader>
                <CardContent><ActivityList ticketId={t.id} /></CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        <aside className="space-y-6" aria-label="Ticket details">
          <TicketControls ticket={t} />
          {isStaff && <AIPanel ticket={t} onUseResponse={setPrefill} />}
          <RelatedArticles ticketId={t.id} />
          {!isStaff && t.status === "RESOLVED" && (
            <Alert variant="success" title="Was your issue resolved?">
              Close the ticket to confirm, or reopen it if you still need help.
            </Alert>
          )}
        </aside>
      </div>
      {!isStaff && (
        <p className="mt-8 text-center text-xs text-slate-400">
          Replies marked "AI-assisted" were drafted with AI and reviewed by a support agent before sending.
        </p>
      )}
      <div className="sr-only" aria-live="polite">{t.ai_insight?.classification_status === "pending" ? "AI analysis in progress" : ""}</div>
    </>
  );
}
