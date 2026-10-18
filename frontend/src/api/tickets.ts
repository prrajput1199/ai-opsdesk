import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AgentOption,
  AIInsight,
  Article,
  Category,
  Paginated,
  ReplyDraft,
  TicketActivity,
  TicketDetail,
  TicketListItem,
  TicketMessage,
  TicketPriority,
  TicketStatus,
} from "@/lib/types";

export interface TicketQuery {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string[];
  priority?: string[];
  category?: string;
  assigned_agent?: string;
  created_after?: string;
  created_before?: string;
  sla?: string;
  ordering?: string;
}

function toParams(q: TicketQuery) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(q)) {
    if (value === undefined || value === "" || value === null) continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v));
    else params.set(key, String(value));
  }
  return params;
}

export const ticketKeys = {
  all: ["tickets"] as const,
  list: (q: TicketQuery) => ["tickets", "list", q] as const,
  detail: (id: number) => ["tickets", "detail", id] as const,
  comments: (id: number) => ["tickets", "detail", id, "comments"] as const,
  activities: (id: number) => ["tickets", "detail", id, "activities"] as const,
  drafts: (id: number) => ["tickets", "detail", id, "drafts"] as const,
  related: (id: number) => ["tickets", "detail", id, "related"] as const,
};

export function useTickets(q: TicketQuery) {
  return useQuery({
    queryKey: ticketKeys.list(q),
    queryFn: async () => (await api.get<Paginated<TicketListItem>>("/tickets/", { params: toParams(q) })).data,
    placeholderData: keepPreviousData,
  });
}

export function useTicket(id: number) {
  return useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: async () => (await api.get<TicketDetail>(`/tickets/${id}/`)).data,
    // While AI classification runs in the background, poll until it finishes.
    refetchInterval: (query) =>
      query.state.data?.ai_insight?.classification_status === "pending" ? 3000 : false,
  });
}

export function useComments(id: number) {
  return useQuery({
    queryKey: ticketKeys.comments(id),
    queryFn: async () => (await api.get<TicketMessage[]>(`/tickets/${id}/comments/`)).data,
  });
}

export function useActivities(id: number) {
  return useQuery({
    queryKey: ticketKeys.activities(id),
    queryFn: async () => (await api.get<TicketActivity[]>(`/tickets/${id}/activities/`)).data,
  });
}

export function useDrafts(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ticketKeys.drafts(id),
    queryFn: async () => (await api.get<ReplyDraft[]>(`/tickets/${id}/drafts/`)).data,
    enabled,
  });
}

export function useRelatedArticles(id: number) {
  return useQuery({
    queryKey: ticketKeys.related(id),
    queryFn: async () => (await api.get<Article[]>(`/tickets/${id}/related-articles/`)).data,
    staleTime: 5 * 60_000,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () => (await api.get<Category[]>("/categories/")).data,
    staleTime: 10 * 60_000,
  });
}

export function useAgents(enabled = true) {
  return useQuery({
    queryKey: ["agents"],
    queryFn: async () => (await api.get<AgentOption[]>("/agents/")).data,
    staleTime: 10 * 60_000,
    enabled,
  });
}

// ---------------------------------------------------------------- mutations ---
function useTicketMutation<TInput, TResult = TicketDetail>(
  id: number,
  fn: (input: TInput) => Promise<TResult>,
  extraInvalidate: (readonly unknown[])[] = [],
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (result) => {
      if (result && typeof result === "object" && "allowed_transitions" in (result as object)) {
        qc.setQueryData(ticketKeys.detail(id), result);
      } else {
        qc.invalidateQueries({ queryKey: ticketKeys.detail(id), exact: true });
      }
      qc.invalidateQueries({ queryKey: ticketKeys.activities(id) });
      qc.invalidateQueries({ queryKey: ["tickets", "list"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
      extraInvalidate.forEach((key) => qc.invalidateQueries({ queryKey: key }));
    },
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { title: string; description: string; category_id?: number | null }) =>
      (await api.post<TicketDetail>("/tickets/", input)).data,
    onSuccess: (ticket) => {
      qc.setQueryData(ticketKeys.detail(ticket.id), ticket);
      qc.invalidateQueries({ queryKey: ["tickets", "list"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useTransition(id: number) {
  return useTicketMutation(id, async (status: TicketStatus) =>
    (await api.post<TicketDetail>(`/tickets/${id}/transition/`, { status })).data,
  );
}

export function useAssign(id: number) {
  return useTicketMutation(id, async (agentId: number | null) =>
    (await api.post<TicketDetail>(`/tickets/${id}/assign/`, { agent_id: agentId })).data,
  );
}

export function useUpdateTicket(id: number) {
  return useTicketMutation(
    id,
    async (input: { priority?: TicketPriority; category_id?: number | null; sla_due_at?: string | null }) =>
      (await api.patch<TicketDetail>(`/tickets/${id}/`, input)).data,
  );
}

export function useAddComment(id: number) {
  return useTicketMutation(
    id,
    async (input: { body: string; is_internal: boolean }) =>
      (await api.post<TicketMessage>(`/tickets/${id}/comments/`, input)).data,
    [ticketKeys.comments(id)],
  );
}

export function useClassify(id: number) {
  return useTicketMutation(id, async () => (await api.post<AIInsight>(`/tickets/${id}/classify/`)).data);
}

export function useSummarize(id: number) {
  return useTicketMutation(id, async () => (await api.post<AIInsight>(`/tickets/${id}/summarize/`)).data);
}

export function useSuggestReply(id: number) {
  return useTicketMutation(
    id,
    async () => (await api.post<ReplyDraft>(`/tickets/${id}/suggest-reply/`)).data,
    [ticketKeys.drafts(id)],
  );
}

export function usePublishDraft(id: number) {
  return useTicketMutation(
    id,
    async (input: { draftId: number; body: string }) =>
      (await api.post<TicketMessage>(`/tickets/${id}/drafts/${input.draftId}/publish/`, { body: input.body })).data,
    [ticketKeys.drafts(id), ticketKeys.comments(id)],
  );
}

export function useDiscardDraft(id: number) {
  return useTicketMutation(
    id,
    async (draftId: number) => (await api.post<ReplyDraft>(`/tickets/${id}/drafts/${draftId}/discard/`)).data,
    [ticketKeys.drafts(id)],
  );
}
