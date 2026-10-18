// Types mirroring the Django REST API responses.

export type Role = "ADMIN" | "AGENT" | "CUSTOMER";
export type TicketStatus = "OPEN" | "IN_PROGRESS" | "WAITING_FOR_CUSTOMER" | "RESOLVED" | "CLOSED";
export type TicketPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export type SLAStatus = "none" | "met" | "breached" | "at_risk" | "on_track";
export type AIStatus = "pending" | "completed" | "failed" | "unavailable" | "";

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Team {
  id: number;
  name: string;
  description: string;
  member_count?: number;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  role: Role;
  team: Team | null;
  date_joined: string;
  last_login: string | null;
}

export interface AdminUser extends User {
  is_active: boolean;
  open_ticket_count: number;
}

export interface UserSummary {
  id: number;
  name: string;
  role: Role;
}

export interface AgentOption {
  id: number;
  name: string;
  email: string;
  role: Role;
  team_id: number | null;
}

export interface Category {
  id: number;
  name: string;
  description: string;
  team: number | null;
  team_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SLAPolicy {
  id: number;
  priority: TicketPriority;
  priority_label: string;
  resolution_hours: number;
  updated_at: string;
}

export interface TicketListItem {
  id: number;
  number: string;
  title: string;
  status: TicketStatus;
  status_label: string;
  priority: TicketPriority;
  priority_label: string;
  category: { id: number; name: string } | null;
  customer: { id: number; name: string; email: string };
  assigned_agent: UserSummary | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  sla_due_at: string | null;
  sla_status: SLAStatus;
  message_count: number;
}

export interface AIInsight {
  classification_status: AIStatus;
  suggested_category: { id: number; name: string } | null;
  suggested_priority: TicketPriority | "";
  suggested_first_response: string;
  needs_human_review: boolean;
  classification_reason: string;
  classified_at: string | null;
  summary: string;
  summary_status: AIStatus;
  summary_updated_at: string | null;
  summary_outdated: boolean;
  error_message: string;
  model_name: string;
}

export interface TicketDetail extends TicketListItem {
  description: string;
  first_response_at: string | null;
  closed_at: string | null;
  ai_insight: AIInsight | null;
  allowed_transitions: TicketStatus[];
  permissions: {
    can_edit: boolean;
    can_assign: boolean;
    can_reply: boolean;
    can_add_internal_note: boolean;
    can_use_ai: boolean;
  };
}

export interface TicketMessage {
  id: number;
  author: UserSummary;
  body: string;
  is_internal: boolean;
  is_ai_assisted: boolean;
  created_at: string;
}

export interface TicketActivity {
  id: number;
  action: string;
  action_label: string;
  actor: UserSummary | null;
  from_value: string;
  to_value: string;
  is_public: boolean;
  created_at: string;
}

export interface ArticleRef {
  id: number;
  title: string;
  slug: string;
}

export interface ReplyDraft {
  id: number;
  body: string;
  status: "draft" | "published" | "discarded";
  requested_by: UserSummary | null;
  referenced_articles: ArticleRef[];
  model_name: string;
  created_at: string;
  decided_at: string | null;
  published_message: number | null;
}

export interface Article {
  id: number;
  title: string;
  slug: string;
  summary: string;
  category: number | null;
  category_name: string | null;
  status: "draft" | "published";
  visibility: "public" | "internal";
  author_name: string | null;
  updated_at: string;
  published_at: string | null;
}

export interface ArticleDetail extends Article {
  content: string;
  created_at: string;
}

export interface SearchResult extends Article {
  headline: string;
  rank: number;
}

export interface KnowledgeAnswer {
  question: string;
  answer: string;
  sufficient_information: boolean;
  ai_generated: boolean;
  citations: ArticleRef[];
  articles_considered: ArticleRef[];
}

export interface AuditLogEntry {
  id: number;
  actor: number | null;
  actor_email: string;
  action: string;
  action_label: string;
  target_type: string;
  target_id: string;
  description: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface DateRangeInfo {
  date_from: string | null;
  date_to: string | null;
}

export interface Overview {
  range: DateRangeInfo;
  total_tickets: number;
  open_tickets: number;
  in_progress_tickets: number;
  waiting_for_customer_tickets: number;
  resolved_tickets: number;
  closed_tickets: number;
  urgent_tickets: number;
  active_tickets: number;
  urgent_active_tickets: number;
  unassigned_active_tickets: number;
  overdue_tickets: number;
  resolved_in_range: number;
  avg_resolution_hours: number | null;
  avg_first_response_hours: number | null;
  sla_compliance_rate: number | null;
}

export interface Trends {
  range: DateRangeInfo;
  series: { date: string; created: number; resolved: number }[];
}

export interface CategoryBreakdown {
  range: DateRangeInfo;
  categories: { category_id: number | null; category: string; total: number; active: number; avg_resolution_hours: number | null }[];
  priorities: { priority: TicketPriority; label: string; total: number }[];
}

export interface ResolutionTime {
  range: DateRangeInfo;
  definition: string;
  resolved_count: number;
  avg_resolution_hours: number | null;
  distribution: { bucket: string; count: number }[];
  by_priority: { priority: TicketPriority; label: string; resolved_count: number; avg_resolution_hours: number | null }[];
}

export interface SLAReport {
  range: DateRangeInfo;
  overdue: number;
  at_risk: number;
  on_track: number;
  resolved_within_sla: number;
  resolved_breached: number;
  compliance_rate: number | null;
  overdue_by_priority: { priority: TicketPriority; label: string; count: number }[];
  policies: { priority: TicketPriority; label: string; resolution_hours: number }[];
  overdue_tickets: {
    id: number;
    number: string;
    title: string;
    priority: TicketPriority;
    status: TicketStatus;
    sla_due_at: string;
    hours_overdue: number;
    assigned_agent: string | null;
  }[];
}

export interface AgentWorkload {
  range: DateRangeInfo;
  agents: {
    id: number;
    name: string;
    email: string;
    team: string | null;
    active: number;
    in_progress: number;
    waiting_for_customer: number;
    urgent: number;
    overdue: number;
    resolved_in_range: number;
    avg_resolution_hours: number | null;
  }[];
}
