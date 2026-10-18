# Architecture

## Components

```mermaid
flowchart LR
    subgraph Browser
        UI[React SPA<br/>TanStack Query · Axios]
    end
    subgraph Edge["Vite dev proxy / nginx / Vercel rewrite"]
        P[/"/api/* → Django"/]
    end
    subgraph Django["Django + DRF (gunicorn)"]
        MW[Middleware<br/>security · CORS · CSRF]
        AUTH[CookieJWTAuthentication<br/>+ CSRF check]
        V[ViewSets / APIViews<br/>permissions · throttles · filters]
        S[Services<br/>tickets · AI · analytics · audit]
        AI[apps.ai<br/>GeminiClient · schemas · prompts]
    end
    DB[(PostgreSQL<br/>tables · indexes · full-text GIN)]
    G[[Google Gemini API]]

    UI -- "same-origin HTTPS<br/>HTTP-only cookies + X-CSRFToken" --> P --> MW --> AUTH --> V --> S
    S --> DB
    S --> AI -- "structured JSON<br/>timeout + retries" --> G
```

| Layer | Responsibility |
|---|---|
| **React SPA** | Pages and components. Server state lives in TanStack Query (cache, refetch, invalidation). It never stores tokens. |
| **Proxy** | Puts the SPA and API on one origin, so auth cookies are first-party and `SameSite=Lax` is enough. |
| **Middleware** | `SecurityMiddleware` (HSTS, nosniff, SSL redirect), WhiteNoise (static files), CORS, CSRF, clickjacking, plus a custom middleware adding CSP / `Cache-Control: no-store` to API responses. |
| **Authentication** | `CookieJWTAuthentication` reads the access JWT from an HTTP-only cookie, validates it, loads the user (rejecting inactive users), then runs Django's CSRF check. |
| **Views** | DRF viewsets. Thin: validate input with serializers, check permissions, call a service, serialize the output. |
| **Services** | Business rules: `tickets/services.py` (transitions, assignment, messages, SLA), `ai/services.py` (all Gemini use), `analytics/services.py` (aggregations), `audit/services.py`. |
| **Selectors** | Read-side access rules: `visible_tickets(user)`, `visible_articles(user)`. Every query starts from these, so authorization can't be forgotten. |
| **apps.ai** | The only module that talks to Gemini: client wrapper (timeouts, retries, error mapping), Pydantic schemas, prompts. |

## Request lifecycle (example: agent changes a ticket's status)

```mermaid
sequenceDiagram
    participant B as Browser
    participant D as Django (middleware)
    participant A as CookieJWTAuthentication
    participant V as TicketViewSet.transition
    participant S as services.transition_ticket
    participant DB as PostgreSQL

    B->>D: POST /api/v1/tickets/42/transition/ {status: RESOLVED}<br/>Cookie: opsdesk_access=…  X-CSRFToken: …
    D->>A: authenticate()
    A->>A: validate JWT, load user, check is_active, enforce CSRF
    A->>V: request.user = agent
    V->>DB: get_object(): visible_tickets(agent).get(pk=42) → 404 if not visible
    V->>V: TransitionSerializer validates input
    V->>S: transition_ticket(ticket, agent, RESOLVED)
    S->>DB: BEGIN, then SELECT … FOR UPDATE
    S->>S: check allowed transition for role, set resolved_at
    S->>DB: UPDATE ticket, INSERT activity, INSERT audit log
    S->>DB: COMMIT
    V-->>B: 200 TicketDetail (status, allowed_transitions, permissions…)
```

If the access token has expired, the API returns **401**. The Axios interceptor calls `POST /auth/refresh/` once; it is shared by all requests that failed at the same time. On success it retries the original request. If refresh fails, the cached user is cleared and the router sends the user to `/login`.

## Authentication & authorization

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as Django
    B->>API: GET /auth/csrf/
    API-->>B: {csrfToken} + csrftoken cookie
    B->>API: POST /auth/login/ {email, password} + X-CSRFToken
    API-->>B: 200 user JSON<br/>Set-Cookie: opsdesk_access (HttpOnly, 15 min, path=/)<br/>Set-Cookie: opsdesk_refresh (HttpOnly, 7 days, path=/api/v1/auth/)
    B->>API: any request (cookie sent automatically) + X-CSRFToken on writes
    API-->>B: 401 when access expired
    B->>API: POST /auth/refresh/ (refresh cookie)
    API-->>B: new access + rotated refresh (old refresh blacklisted)
    B->>API: POST /auth/logout/
    API-->>B: refresh blacklisted, cookies deleted
```

- Tokens are **never** in a JSON body or `localStorage`; JavaScript cannot read them (HTTP-only).
- The refresh cookie's `path` limits it to `/api/v1/auth/`, so it isn't sent with ordinary requests.
- **CSRF** is enforced for every cookie-authenticated write, including login and register (to block login-CSRF).
- **Rotation + blacklist:** each refresh issues a new refresh token and blacklists the old one, so a stolen, already-used refresh token is useless. A password change blacklists all of the user's refresh tokens.
- **Roles:** `User.role` ∈ {ADMIN, AGENT, CUSTOMER}. Public registration always creates CUSTOMER. Role checks happen in permission classes (`apps/core/permissions.py`), in services (e.g. who may assign), and in selectors (what you may see).

### Who can see which ticket (`apps/tickets/selectors.py`)

| Role | Visible tickets |
|---|---|
| Admin | all |
| Agent | assigned to them **or** in a category routed to their team **or** unassigned and not routed to any team (shared queue) |
| Customer | only their own |

Objects outside this set return **404** rather than 403, so ticket IDs can't be enumerated.

### Status transitions (`apps/tickets/services.py`)

```mermaid
stateDiagram-v2
    [*] --> OPEN
    OPEN --> IN_PROGRESS
    OPEN --> WAITING_FOR_CUSTOMER
    OPEN --> RESOLVED
    IN_PROGRESS --> OPEN
    IN_PROGRESS --> WAITING_FOR_CUSTOMER
    IN_PROGRESS --> RESOLVED
    WAITING_FOR_CUSTOMER --> IN_PROGRESS : agent, or customer replies
    WAITING_FOR_CUSTOMER --> RESOLVED
    RESOLVED --> IN_PROGRESS : agent reopens
    RESOLVED --> OPEN : customer reopens
    OPEN --> CLOSED
    IN_PROGRESS --> CLOSED
    WAITING_FOR_CUSTOMER --> CLOSED
    RESOLVED --> CLOSED
    CLOSED --> [*]
```

Customers may only close their ticket (any active state) or confirm/reopen a resolution. Staff may make every other move shown. `CLOSED` is final; a closed ticket accepts no messages or edits.

## AI workflow

```mermaid
flowchart TD
    C[Customer creates ticket] --> T[(Ticket saved<br/>+ AI insight 'pending')]
    T -- "after COMMIT<br/>(background thread)" --> CL[classify_ticket]
    CL --> G1{Gemini call<br/>response_schema=ClassificationResult}
    G1 -- ok --> V1[Pydantic validation<br/>unknown category → needs review]
    V1 --> I[(Insight 'completed'<br/>suggestions only)]
    G1 -- "timeout / 5xx / 429 / invalid JSON" --> F[(Insight 'failed'<br/>safe error message)]
    G1 -- no API key --> U[(Insight 'unavailable')]
    I --> AG[Agent reviews]
    AG -- "Apply suggestions" --> PATCH[PATCH ticket<br/>normal permissions + audit]
    AG -- "Draft a reply" --> R[suggest_reply<br/>+ related published KB excerpts]
    R --> D[(ReplyDraft 'draft'<br/>invisible to customer)]
    D -- "agent edits + Approve & send" --> M[(Public message<br/>is_ai_assisted=true · audit log)]
    D -- Discard --> X[(Draft 'discarded')]
```

Safety properties:

1. **AI never acts on its own.** Classification only stores *suggestions*; an agent clicks "Apply". Reply drafts are invisible to customers until an agent publishes them, and every publication is audited.
2. **Structured output, validated twice.** The Pydantic model is sent as `response_schema` (Gemini returns JSON in that shape) *and* used locally with `model_validate_json`. Enums (priority) are constrained; text is trimmed and length-limited; empty answers are rejected.
3. **Citations can't be invented.** For KB answers and reply drafts, `used_article_ids` is intersected with the IDs actually sent in the prompt. If no article matches the question, Gemini isn't called at all and the API says the knowledge base doesn't cover it.
4. **Least data.** Prompts contain ticket text and role labels ("Customer", "Support agent"), not names or emails. Customer-facing features (KB answers, reply drafts) only use **published** articles the user may read; internal notes are only included in the agent-facing summary.
5. **Prompt-injection hygiene.** User text is wrapped in tags and the system instruction says to treat it as data. Combined with (1), a malicious ticket can at worst produce a bad suggestion that a human sees.
6. **Failure isolation.** Timeouts (20 s), one retry with backoff for 429/5xx/network errors, an input cap (`AI_MAX_INPUT_CHARS`), per-user AI rate limits, and mapping to safe messages (`503`/`429`). Ticket creation never waits for or depends on Gemini.

## Database schema

```mermaid
erDiagram
    TEAM ||--o{ USER : "members"
    TEAM ||--o{ CATEGORY : "routes"
    USER ||--o{ TICKET : "customer (PROTECT)"
    USER ||--o{ TICKET : "assigned_agent (SET_NULL)"
    CATEGORY ||--o{ TICKET : "category (SET_NULL)"
    TICKET ||--o{ TICKET_MESSAGE : "CASCADE"
    TICKET ||--o{ TICKET_ACTIVITY : "CASCADE"
    TICKET ||--|| TICKET_AI_INSIGHT : "CASCADE"
    TICKET ||--o{ REPLY_DRAFT : "CASCADE"
    REPLY_DRAFT }o--o{ KB_ARTICLE : "referenced_articles"
    REPLY_DRAFT |o--o| TICKET_MESSAGE : "published_message"
    CATEGORY ||--o{ KB_ARTICLE : "category (SET_NULL)"
    USER ||--o{ AUDIT_LOG : "actor (SET_NULL)"

    USER {
        bigint id PK
        string email UK
        string role
        bigint team_id FK
        bool is_active
    }
    TICKET {
        bigint id PK
        string number UK
        string title
        text description
        string status
        string priority
        datetime created_at
        datetime resolved_at
        datetime closed_at
        datetime first_response_at
        datetime sla_due_at
    }
    TICKET_MESSAGE {
        bigint id PK
        text body
        bool is_internal
        bool is_ai_assisted
        datetime created_at
    }
    TICKET_ACTIVITY {
        bigint id PK
        string action
        string from_value
        string to_value
        bool is_public
    }
    TICKET_AI_INSIGHT {
        string classification_status
        string suggested_priority
        text summary
        bool needs_human_review
    }
    REPLY_DRAFT {
        bigint id PK
        text body
        string status
    }
    SLA_POLICY {
        string priority UK
        int resolution_hours
    }
    KB_ARTICLE {
        bigint id PK
        string slug UK
        text content
        string status
        string visibility
    }
    AUDIT_LOG {
        bigint id PK
        string action
        string target_type
        string target_id
        json metadata
        inet ip_address
    }
```

Design decisions:

- **Deletion behaviour:** customers and message authors are `PROTECT` (history must not vanish; users are *deactivated*, never deleted); assignee/category are `SET_NULL`; a ticket's messages/activities/insight/drafts `CASCADE` with it; audit logs keep `actor_email` as a snapshot.
- **Constraints:** check constraints on role/status/priority/visibility values, `resolved_at >= created_at`, SLA hours ≥ 1, unique ticket number, slug and email.
- **Indexes:** `(status, priority)`, `(customer, -created_at)`, `(assigned_agent, status)`, `sla_due_at`, `resolved_at`, `(ticket, created_at)` on messages/activities, `(action, created_at)` and `(target_type, target_id)` on audit logs, and a **GIN expression index** on `to_tsvector(title) || to_tsvector(content)` for full-text search.
- **Ticket numbers** (`OPS-000123`) are derived from the primary key inside the creating transaction. That's simple, unique and sequential, and avoids a separate counter table.
- **Activity vs. audit log:** `TicketActivity` is the user-facing timeline of one ticket (some entries are public to the customer). `AuditLog` is the security and compliance trail across the whole system (logins, user changes, publications), visible to admins only and read-only.

## Analytics & SLA

All metrics are single SQL aggregations (`COUNT(*) FILTER (WHERE …)`, `AVG(resolved_at - created_at)`, `GROUP BY date_trunc('day', …)`) run against the user's `visible_tickets` queryset, so agents only see their scope and customers only their own tickets. Agent workload (admins only) is one annotated query over users with filtered `COUNT`/`AVG` on the joined tickets.

- SLA deadline = `created_at + SLAPolicy.resolution_hours` for the ticket's priority, recomputed when the priority changes (unless an agent sets a manual deadline).
- `sla_status`: `met`/`breached` once resolved (comparing `resolved_at` to the deadline). For active tickets: `breached` when past the deadline, `at_risk` with < 25 % of the window left, otherwise `on_track`.
- Resolution time counts only tickets with a `resolved_at`; unresolved tickets and tickets closed without a resolution are excluded, and reopened tickets measure to their latest resolution.

## Frontend structure

- `src/lib/api.ts`: Axios instance with `withCredentials`, CSRF header injection, single-flight refresh on 401, and DRF error formatting.
- `src/api/*.ts`: one TanStack Query hook per endpoint; mutations invalidate the related caches (ticket detail, lists, analytics).
- `src/context/AuthContext.tsx`: the current user (from `/auth/me/`) plus role helpers.
- `src/components/layout/ProtectedRoute.tsx`: route guards by role, mirroring the API rules for UX (the API remains the enforcement point).
- `src/components/ui/*`: small shadcn-style components (Radix for dialog/menu/tabs; native `<select>` for accessibility).
- Pages are lazy-loaded; filters on the ticket list live in the URL so views can be shared and survive reloads.
