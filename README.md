# AI OpsDesk — AI-Powered Support Ticket Intelligence Platform

A full-stack customer-support platform. Customers submit tickets, agents resolve them, admins run the operation, and **Google Gemini** helps with triage, summaries, reply drafts and knowledge-base answers. A human approves any AI output before a customer sees it.

**Stack:** Django 5.2 · Django REST Framework · PostgreSQL · JWT in HTTP-only cookies · Gemini (`google-genai`) · React 18 + TypeScript + Vite · Tailwind CSS · TanStack Query · React Hook Form + Zod · Recharts

---

## Features

| Area | What's included |
|---|---|
| **Roles** | Admin, Agent, Customer, enforced in the API (not only hidden in the UI). Other customers' tickets return **404**, so IDs can't be probed. |
| **Auth** | Customer registration, login/logout, JWT access + refresh tokens in **HTTP-only cookies**, CSRF protection, token rotation and blacklisting, password change (signs out other devices), rate limiting |
| **Tickets** | Ticket numbers (`OPS-000123`), 5 statuses with validated transitions per role, 4 priorities, categories, assignment rules, public replies + internal notes, activity history, search/filter/sort/pagination |
| **SLA** | Resolution targets per priority (editable by admins), deadlines, on-track / at-risk / breached / met states, overdue filters and reports |
| **AI (Gemini)** | Auto-classification on create (category, priority, summary, first reply, needs-review flag), summaries you can regenerate, reply drafts grounded in KB articles, KB question answering with **citations limited to the articles supplied**. Structured JSON output validated with Pydantic, timeouts, retries, rate limits, and a visible fallback when AI is unavailable. |
| **Knowledge base** | Public/internal articles, drafts, PostgreSQL full-text search with highlighted excerpts, "suggested articles" while writing a ticket |
| **Analytics** | Overview, created vs. resolved trend, category/priority breakdown, resolution-time distribution, SLA report, agent workload. All computed with PostgreSQL aggregation, scoped to what each user may see. |
| **Admin** | Staff accounts (create, change role/team, deactivate), teams, categories & routing, SLA targets, **read-only audit log** |
| **Quality** | 119 backend tests (pytest, real PostgreSQL, Gemini mocked), 18 frontend tests (Vitest + Testing Library), OpenAPI/Swagger docs |

Screens: login, registration, dashboard (per role), ticket list, create ticket, ticket detail with conversation, AI panel and activity history, knowledge base list/article/editor, search & ask AI, analytics, users & agents, categories & SLA, audit log, profile, 404.

More documentation:
- [ARCHITECTURE.md](ARCHITECTURE.md): components, data flow, auth, AI workflow, schema
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md): every endpoint, with examples
- [INTERVIEW_PREPARATION.md](INTERVIEW_PREPARATION.md): how it works and 35 interview questions

---

## Project structure

```
ai-opsdesk/
├── backend/                 Django project
│   ├── config/              settings, urls, wsgi/asgi, test settings
│   ├── apps/
│   │   ├── accounts/        custom User (roles), teams, cookie-JWT auth, user admin API
│   │   ├── tickets/         tickets, messages, activities, SLA, AI insights & drafts, seed command
│   │   ├── knowledge_base/  articles + PostgreSQL full-text search
│   │   ├── ai/              Gemini client, schemas, prompts, AI services (the only code that calls Gemini)
│   │   ├── analytics/       aggregation queries + endpoints
│   │   ├── audit/           audit log model, service, read-only API
│   │   └── core/            permissions, pagination, throttling, error handling, security headers
│   ├── tests/               pytest suite
│   ├── requirements.txt / requirements-dev.txt
│   └── Dockerfile, docker-entrypoint.sh, .env.example
├── frontend/                React + TypeScript (Vite)
│   ├── src/api/             TanStack Query hooks per API area
│   ├── src/components/      ui/ (shadcn-style), layout/, tickets/, analytics/
│   ├── src/pages/           one file per screen
│   ├── src/lib/             axios client (CSRF + refresh), types, utils
│   └── src/test/            Vitest tests
├── docker-compose.yml
└── *.md docs
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | **3.12 or 3.13** | Tested on 3.13; the Docker image uses 3.12 |
| Node.js | **20 or 22 LTS** | Tested on 22 |
| PostgreSQL | **14+** | Tested on 16. Full-text search needs PostgreSQL (SQLite is not supported). |
| Gemini API key | optional | Free key from <https://aistudio.google.com/apikey>. Without one, the app works and shows "AI not configured". |

---

## Local setup (step by step)

### 1. PostgreSQL: create a database and user

Open `psql` as the postgres superuser (Windows: "SQL Shell (psql)" from the Start menu; macOS/Linux: `psql -U postgres` or `sudo -u postgres psql`) and run:

```sql
CREATE USER opsdesk WITH PASSWORD 'opsdesk' CREATEDB;
CREATE DATABASE opsdesk OWNER opsdesk;
```

`CREATEDB` lets the test runner create its temporary test database.

### 2. Backend

**macOS / Linux**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

**Windows PowerShell**
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `backend/.env`:
- `DJANGO_SECRET_KEY`: generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DATABASE_URL`: matches step 1 by default (`postgres://opsdesk:opsdesk@localhost:5432/opsdesk`)
- `GEMINI_API_KEY`: paste your key (optional)
- Keep `DJANGO_DEBUG=True` for local development (cookies then work over plain `http://localhost`)

Then (same commands on every OS, inside the activated virtualenv):

```bash
python manage.py migrate             # creates tables + default SLA policies
python manage.py seed_demo           # demo users, categories, articles, ~45 tickets (DEBUG only)
python manage.py runserver           # http://localhost:8000
```

Optional: create your own admin account (it can also log in to Django admin at <http://localhost:8000/admin/>):
```bash
python manage.py createsuperuser     # gets role=ADMIN automatically
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```
(Windows PowerShell: the same commands. Optionally `Copy-Item .env.example .env` / `cp .env.example .env`; the defaults already work.)

Open **<http://localhost:5173>**. The Vite dev server proxies `/api` to Django, so the browser sees a single origin and the auth cookies stay first-party.

### Demo accounts (local development only)

Created by `seed_demo`. The password for all of them is **`OpsDesk@2026`** (or your `DEMO_PASSWORD`).

| Role | Email |
|---|---|
| Admin | `admin@opsdesk.dev` |
| Agent (Technical Support) | `priya.agent@opsdesk.dev`, `neha.agent@opsdesk.dev` |
| Agent (Billing) | `rahul.agent@opsdesk.dev` |
| Customer | `customer@opsdesk.dev`, `sara.customer@opsdesk.dev`, `john.customer@opsdesk.dev` |

`python manage.py seed_demo --reset` wipes tickets and articles and recreates them. The seed never fabricates AI output: open a ticket as an agent and click **Run** in the AI panel to generate real insights.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `DJANGO_DEBUG` | `False` | `True` only for local development |
| `DJANGO_SECRET_KEY` | **required** | Long random string |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `DJANGO_TIME_ZONE` | `UTC` | Used for day buckets in analytics |
| `DATABASE_URL` | **required** | `postgres://user:pass@host:5432/db` |
| `DB_CONN_MAX_AGE` | `60` | Persistent DB connection lifetime (seconds) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,…` | Only needed if the frontend is on another origin |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:5173,…` | Origins allowed to make unsafe requests |
| `AUTH_COOKIE_SECURE` | `not DEBUG` | Send cookies only over HTTPS (keep `True` in production) |
| `AUTH_COOKIE_SAMESITE` | `Lax` | `None` only for cross-site setups (requires Secure) |
| `AUTH_COOKIE_DOMAIN` | unset | Optional cookie domain |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS` | `15` / `7` | Token lifetimes |
| `JWT_SIGNING_KEY` | `DJANGO_SECRET_KEY` | Optional separate JWT key |
| `GEMINI_API_KEY` | empty | Empty = AI features show a "not configured" state |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any Gemini model that supports structured output |
| `GEMINI_TIMEOUT_SECONDS` | `20` | Per-request timeout |
| `GEMINI_MAX_RETRIES` | `1` | Retries for 429/5xx/network errors |
| `AI_MAX_INPUT_CHARS` | `12000` | Hard cap on prompt size |
| `AI_CLASSIFICATION_MODE` | `thread` | `thread` (background after commit), `sync`, or `off` |
| `THROTTLE_AUTH` / `THROTTLE_REGISTER` / `THROTTLE_AI` | `10/min` / `5/min` / `20/min` | Rate limits (also `THROTTLE_ANON`, `THROTTLE_USER`) |
| `SECURE_SSL_REDIRECT` | `True` when not DEBUG | Redirect HTTP→HTTPS |
| `SECURE_HSTS_SECONDS` | `2592000` when not DEBUG | HSTS max-age |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False` | Enable only if every subdomain is HTTPS |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | `1048576` | Max request body (bytes) |
| `LOG_LEVEL` | `INFO` | Root log level |
| `DEMO_PASSWORD` | `OpsDesk@2026` | Password for `seed_demo` accounts |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | API base URL as seen by the browser. Keep the relative default behind a proxy/rewrite (recommended). |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Dev server proxy target |

---

## Running tests

**Backend** (needs PostgreSQL running; uses `config/test_settings.py`, and Gemini is always mocked):
```bash
cd backend
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pytest                               # 119 tests
```
If your database URL differs from the default, set it first: `export DATABASE_URL=postgres://…` (PowerShell: `$env:DATABASE_URL="postgres://…"`).

**Frontend:**
```bash
cd frontend
npm test                             # Vitest, 18 tests
npm run typecheck                    # TypeScript strict mode
```

---

## API documentation

With the backend running:
- Swagger UI: <http://localhost:8000/api/v1/docs/>
- ReDoc: <http://localhost:8000/api/v1/redoc/>
- Raw schema: <http://localhost:8000/api/v1/schema/>
- Generate a file: `python manage.py spectacular --file openapi.yml --validate`

Swagger "Try it out" uses your browser cookies: log in through the frontend first (cookies are shared across `localhost` ports). Unsafe requests also need an `X-CSRFToken` header; get one from `GET /api/v1/auth/csrf/`. See [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

---

## Production build

```bash
# Frontend: static files in frontend/dist
cd frontend && npm ci && npm run build

# Backend
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --threads 4 --timeout 60
```

Checklist: `DJANGO_DEBUG=False`, strong `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, HTTPS everywhere, `AUTH_COOKIE_SECURE=True` (the default when not DEBUG), and **never** run `seed_demo` on a real database. Run `python manage.py check --deploy` before going live.

### Docker (production-like, local)

```bash
docker compose up --build            # http://localhost:8080 (API also on :8000)
```
This starts PostgreSQL, Django (gunicorn) and nginx. nginx serves the React build and proxies `/api` to Django, so everything is same-origin. Demo data is seeded (`SEED_DEMO_DATA=true`). To enable AI, export `GEMINI_API_KEY` before running. The compose file disables Secure cookies and the HTTPS redirect **only** because it serves plain HTTP on localhost.

### Deployment (example: Render + Vercel + Neon)

1. **Database:** create a PostgreSQL database (Neon, Supabase, Render) and copy its connection string.
2. **Backend (Render web service):** root directory `backend`, build `pip install -r requirements.txt && python manage.py collectstatic --noinput`, pre-deploy command `python manage.py migrate`, start `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 4 --timeout 60`. Set the env vars above (`DJANGO_DEBUG=False`, `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=<your-api>.onrender.com`, `CSRF_TRUSTED_ORIGINS=https://<your-app>.vercel.app`, `GEMINI_API_KEY`). The Dockerfile works too.
3. **Frontend (Vercel):** root directory `frontend`, framework Vite. Edit `frontend/vercel.json` and replace `YOUR-BACKEND.onrender.com` with your backend host. Vercel then proxies `/api/*` to Django, so cookies stay first-party and `SameSite=Lax` works. Keep `VITE_API_BASE_URL=/api/v1`.
4. Alternative without a proxy (different sites): set `VITE_API_BASE_URL=https://api.example.com/api/v1`, `AUTH_COOKIE_SAMESITE=None`, `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to the frontend URL. Third-party cookies are blocked by some browsers, which is why the proxy is recommended.

`AI_CLASSIFICATION_MODE=thread` runs classification in a background thread inside the web process. That's fine for an MVP; under heavy load use a task queue (see Limitations).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `django.core.exceptions.ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable` | Create `backend/.env` from `.env.example` and fill it in |
| `connection refused` / `password authentication failed` | Check PostgreSQL is running and that `DATABASE_URL` matches the user/password/database you created |
| `relation "…" does not exist` | Run `python manage.py migrate` |
| Tests fail with `permission denied to create database` | `ALTER USER opsdesk CREATEDB;` |
| Logged in but every request is 401 | With `DJANGO_DEBUG=False` over plain HTTP, cookies are Secure and the browser drops them. Use `DJANGO_DEBUG=True` locally or set `AUTH_COOKIE_SECURE=False` (local only). |
| `CSRF Failed: Origin checking failed` | Add the frontend origin to `CSRF_TRUSTED_ORIGINS` |
| `/admin/users` opens the Django admin login | Don't proxy `/admin` to Django; that path belongs to the React app. Use `http://localhost:8000/admin/` for Django admin. |
| AI panel says "AI is not configured" | Set `GEMINI_API_KEY` in `backend/.env` and restart the server |
| AI says "temporarily unavailable" or "too many requests" | Gemini timeout, outage or quota (HTTP 429). Retry later, or check the key and model name (`GEMINI_MODEL`). The rest of the app keeps working. |
| `seed_demo only runs with DJANGO_DEBUG=True` | Intentional. Use `--allow-production` only for throwaway demo databases. |
| PowerShell: "running scripts is disabled" | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port 8000 or 5173 already in use | `python manage.py runserver 8001` and set `VITE_PROXY_TARGET=http://localhost:8001`; or `npm run dev -- --port 5174` (then add that origin to `CSRF_TRUSTED_ORIGINS`) |

---

## Known limitations

- **Background work runs in a thread, not a queue.** Classification after ticket creation runs in a daemon thread. If the process restarts mid-call, that classification is lost (the ticket is fine, and an agent can click "Re-run"). Production at scale should use Celery/RQ with Redis.
- **Rate limits use Django's local-memory cache**, which is per process. With several gunicorn workers or servers, configure a shared cache (Redis) for exact limits.
- **No file attachments** on tickets (out of scope for this version).
- **No email notifications or real-time updates.** The UI refreshes on actions and polls only while AI classification is pending.
- **Keyword/full-text search only** for the knowledge base (no embeddings or vector search), so synonyms the text doesn't contain won't match.
- **SLA uses wall-clock hours**, not business hours or holidays.
- **AI quality depends on the model.** Output is validated for shape, not for truth, which is why a human must approve everything customer-facing.
- **Not verified in this build environment:** real Gemini API calls (all AI tests use a mocked client; the SDK's handling of the response schemas was checked offline) and building the Docker images (Docker Hub was unreachable; the compose file and entrypoint were validated, and the same commands were run outside Docker).
