# API Documentation

Base URL: `/api/v1/`. Interactive docs, generated from the code by drf-spectacular: **`/api/v1/docs/`** (Swagger), `/api/v1/redoc/`, and the raw schema at `/api/v1/schema/`.

## Conventions

- **Auth:** HTTP-only cookies (`opsdesk_access`, `opsdesk_refresh`) set by login/register/refresh. Send requests with credentials (`fetch(…, {credentials: "include"})` / Axios `withCredentials: true`).
- **CSRF:** every `POST/PATCH/PUT/DELETE` needs the header `X-CSRFToken: <token>`. Get the token from `GET /auth/csrf/`.
- **Format:** JSON request and response bodies. Timestamps are ISO-8601 in UTC.
- **Pagination:** list endpoints return `{count, next, previous, results}`; use `?page=2&page_size=50` (max 100).
- **Errors:**

| Status | Meaning | Body |
|---|---|---|
| 400 | Validation failed | `{"field": ["message"]}` or `{"detail": "…"}` |
| 401 | Not logged in / token expired (call `/auth/refresh/`) | `{"detail": "…"}` |
| 403 | Logged in but not allowed (role), or CSRF failed | `{"detail": "…"}` |
| 404 | Doesn't exist **or you may not see it** | `{"detail": "Not found."}` |
| 429 | Rate limit (login, register, AI endpoints) or Gemini quota | `{"detail": "…"}` |
| 503 | AI temporarily unavailable or not configured | `{"detail": "…"}` |
| 500 | Unexpected error (details are logged, never returned) | `{"detail": "An unexpected error occurred…"}` |

Role legend: 🅰 Admin · 🅶 Agent · 🅲 Customer · 🌐 anyone.

---

## Authentication

| Method & path | Who | Description |
|---|---|---|
| `GET /auth/csrf/` | 🌐 | Returns `{"csrfToken": "…"}` and sets the `csrftoken` cookie |
| `POST /auth/register/` | 🌐 | `{email, first_name, last_name, password}` → 201 user; sets cookies. Always creates a **customer**. 5/min. |
| `POST /auth/login/` | 🌐 | `{email, password}` → 200 user; sets cookies. Same 401 message for every failure. 10/min. |
| `POST /auth/refresh/` | 🌐 (refresh cookie) | Rotates the refresh token and issues a new access token. 401 + cookies cleared if invalid. |
| `POST /auth/logout/` | 🌐 | Blacklists the refresh token, clears cookies → 205 |
| `GET /auth/me/` | logged in | Current user |
| `PATCH /auth/me/` | logged in | `{first_name, last_name}` (email and role are read-only) |
| `POST /auth/change-password/` | logged in | `{current_password, new_password}`; signs out other devices |

```http
POST /api/v1/auth/login/
X-CSRFToken: 7Gq…
Content-Type: application/json

{"email": "priya.agent@opsdesk.dev", "password": "OpsDesk@2026"}
```
```json
{"id": 2, "email": "priya.agent@opsdesk.dev", "first_name": "Priya", "last_name": "Sharma",
 "name": "Priya Sharma", "role": "AGENT", "team": {"id": 1, "name": "Technical Support", ...},
 "date_joined": "...", "last_login": "..."}
```

---

## Tickets

| Method & path | Who | Description |
|---|---|---|
| `GET /tickets/` | 🅰🅶🅲 | Tickets you can see (customers: own; agents: assigned, team, shared queue; admins: all) |
| `POST /tickets/` | 🅲 | `{title (5–200), description (10–5000), category_id?}` → 201 detail. Status, priority and assignee are set by the server; extra fields are ignored. |
| `GET /tickets/{id}/` | 🅰🅶🅲 | Detail incl. `allowed_transitions`, `permissions`, and `ai_insight` (always `null` for customers) |
| `PATCH /tickets/{id}/` | 🅰🅶 | `{priority?, category_id?, sla_due_at?}`. Changing priority recomputes the SLA deadline. |
| `POST /tickets/{id}/transition/` | 🅰🅶🅲 | `{status}`, validated against the allowed transitions for your role |
| `POST /tickets/{id}/assign/` | 🅰🅶 | `{agent_id}` (or `null` to unassign, admin only). Agents can only take an unassigned ticket for themselves. |
| `GET /tickets/{id}/comments/` | 🅰🅶🅲 | Conversation (internal notes are excluded for customers) |
| `POST /tickets/{id}/comments/` | 🅰🅶🅲 | `{body, is_internal?}`. Customers get 403 for `is_internal: true`. 400 on closed tickets. |
| `GET /tickets/{id}/activities/` | 🅰🅶🅲 | Timeline (customers see public entries only) |
| `GET /tickets/{id}/related-articles/` | 🅰🅶🅲 | KB articles matching the ticket (filtered to what you may read) |

**List filters:** `status` (repeatable), `priority` (repeatable), `category`, `assigned_agent` (`<id>`, `me`, `unassigned`), `created_after`, `created_before` (YYYY-MM-DD), `sla` (`overdue` \| `breached`), `search` (number or title), `ordering` (`created_at`, `updated_at`, `priority_rank`, `sla_due_at`; prefix `-` for descending).

```http
GET /api/v1/tickets/?status=OPEN&status=IN_PROGRESS&assigned_agent=me&ordering=-priority_rank&page_size=20
```
```json
{"count": 7, "next": null, "previous": null, "results": [
  {"id": 97, "number": "OPS-000097", "title": "Production outage - all users see error 500",
   "status": "IN_PROGRESS", "status_label": "In Progress", "priority": "URGENT", "priority_label": "Urgent",
   "category": {"id": 1, "name": "Technical Issue"},
   "customer": {"id": 7, "name": "John Dsouza", "email": "john.customer@opsdesk.dev"},
   "assigned_agent": {"id": 2, "name": "Priya Sharma", "role": "AGENT"},
   "created_at": "...", "updated_at": "...", "resolved_at": null, "sla_due_at": "...",
   "sla_status": "breached", "message_count": 3}
]}
```

Detail-only fields:
```json
{
  "description": "...", "first_response_at": "...", "closed_at": null,
  "allowed_transitions": ["OPEN", "WAITING_FOR_CUSTOMER", "RESOLVED", "CLOSED"],
  "permissions": {"can_edit": true, "can_assign": false, "can_reply": true, "can_add_internal_note": true, "can_use_ai": true},
  "ai_insight": {
    "classification_status": "completed", "suggested_category": {"id": 3, "name": "Billing"},
    "suggested_priority": "HIGH", "suggested_first_response": "...", "needs_human_review": true,
    "classification_reason": "...", "summary": "...", "summary_status": "completed",
    "summary_outdated": false, "error_message": "", "model_name": "gemini-2.5-flash"
  }
}
```

### Ticket AI endpoints (🅰🅶, rate-limited per user, `THROTTLE_AI`)

| Method & path | Description |
|---|---|
| `POST /tickets/{id}/classify/` | Re-run classification. 200 insight; **503** if Gemini fails or isn't configured (state is recorded on the insight). |
| `POST /tickets/{id}/summarize/` | Regenerate the summary (includes internal notes, agent-facing). 200 insight / 503 / 429. |
| `POST /tickets/{id}/suggest-reply/` | Create a **draft** using the conversation and related published KB articles. 201 draft / 503 / 429. Never visible to the customer. |
| `GET /tickets/{id}/drafts/` | Recent drafts |
| `POST /tickets/{id}/drafts/{draft_id}/publish/` | `{body}` (edited text). Posts a public reply with `is_ai_assisted: true`; audited. |
| `POST /tickets/{id}/drafts/{draft_id}/discard/` | Mark the draft discarded |

```json
// 201 POST /tickets/42/suggest-reply/
{"id": 9, "status": "draft", "body": "Hello, ...\n\nThe Support Team",
 "referenced_articles": [{"id": 4, "title": "Refund and cancellation policy", "slug": "refund-and-cancellation-policy"}],
 "model_name": "gemini-2.5-flash", "requested_by": {"id": 4, "name": "Rahul Nair", "role": "AGENT"},
 "created_at": "...", "decided_at": null, "published_message": null}
```

---

## Knowledge base

| Method & path | Who | Description |
|---|---|---|
| `GET /knowledge-base/articles/` | 🅰🅶🅲 | Customers: published + public. Agents: published (incl. internal). Admins: all incl. drafts. Filters `category`, `status`, `visibility`, `search` (title/summary). |
| `GET /knowledge-base/articles/{id}/` | same | Includes `content` |
| `POST /knowledge-base/articles/` | 🅰 | `{title, content, summary?, category?, status, visibility, slug?}`; the slug is generated and made unique |
| `PATCH/DELETE /knowledge-base/articles/{id}/` | 🅰 | Audited |
| `GET /knowledge-base/search/?q=…&limit=10` | 🅰🅶🅲 | PostgreSQL full-text search, ranked (title weighted above content), with a `headline` excerpt where matches are wrapped in `<<…>>` |
| `POST /knowledge-base/ask/` | 🅰🅶🅲 | `{question (5–500)}`, answered **only** from matching published articles you may read |

```json
// POST /knowledge-base/ask/  {"question": "How do I reset my password?"}
{"question": "How do I reset my password?",
 "answer": "Open the login page and click Forgot password...",
 "sufficient_information": true, "ai_generated": true,
 "citations": [{"id": 1, "title": "How to reset your password", "slug": "how-to-reset-your-password"}],
 "articles_considered": [{"id": 1, ...}, {"id": 2, ...}]}
```
If no article matches, Gemini is not called: `{"sufficient_information": false, "ai_generated": false, "citations": [], ...}`.

---

## Analytics

All accept `date_from` / `date_to` (YYYY-MM-DD, inclusive, max 366 days). Data is scoped to the tickets the caller can see.

| Path | Who | Returns |
|---|---|---|
| `GET /analytics/overview/` | 🅰🅶🅲 | Counts by status, urgent, active / unassigned / overdue right now, avg resolution & first-response hours, SLA compliance % |
| `GET /analytics/ticket-trends/` | 🅰🅶 | `series: [{date, created, resolved}]`, one entry per day (default: last 30 days) |
| `GET /analytics/category-breakdown/` | 🅰🅶 | `categories: [{category, total, active, avg_resolution_hours}]`, `priorities: [{priority, total}]` |
| `GET /analytics/resolution-time/` | 🅰🅶 | Average, distribution buckets (≤4h, 4–24h, 1–3d, >3d), per-priority averages, and the definition used |
| `GET /analytics/sla/` | 🅰🅶 | overdue / at-risk / on-track now, met vs. breached in range, compliance %, policies, top-10 overdue tickets |
| `GET /analytics/agent-workload/` | 🅰 | Per agent: active, in progress, waiting, urgent, overdue, resolved in range, avg resolution |

---

## Administration

| Method & path | Who | Description |
|---|---|---|
| `GET /users/` | 🅰 | Filters `role`, `is_active`, `team`; `search`; includes `open_ticket_count` |
| `POST /users/` | 🅰 | Create staff: `{email, first_name, last_name, role: AGENT\|ADMIN, team_id?, password}` |
| `PATCH /users/{id}/` | 🅰 | `{first_name?, last_name?, role?, team_id?, is_active?}`. Deactivating revokes sessions; you can't deactivate or demote yourself; customers can't be promoted. |
| `GET /agents/` | 🅰🅶 | Active agents/admins (for dropdowns) |
| `GET/POST/PATCH/DELETE /teams/` | read 🅰🅶, write 🅰 | Teams with `member_count` |
| `GET /categories/` | 🅰🅶🅲 | Active categories (admins also see inactive ones) |
| `POST/PATCH/DELETE /categories/{id}/` | 🅰 | `{name, description?, team?, is_active?}`. Delete is refused if tickets use the category (deactivate instead). |
| `GET /sla-policies/` | 🅰🅶 | Resolution hours per priority |
| `PATCH /sla-policies/{id}/` | 🅰 | `{resolution_hours: 1..2160}` |
| `GET /audit-logs/` | 🅰 | Read-only. Filters `action`, `actor`, `target_type`, `target_id`, `date_from`, `date_to`; `search` |
| `GET /health/` | 🌐 | `{"status": "ok", "database": "ok"}` (503 if the DB is down) |

## Rate limits

| Scope | Default | Applies to |
|---|---|---|
| `auth` | 10/min per IP | login, change-password |
| `register` | 5/min per IP | registration |
| `ai` | 20/min per user | classify, summarize, suggest-reply, ask |
| `anon` / `user` | 60/min / 600/min | everything else |
