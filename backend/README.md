# AI OpsDesk — Backend (Django + DRF)

See the [root README](../README.md) for full setup, environment variables and deployment.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env                                     # Windows: Copy-Item .env.example .env  (then edit it)
python manage.py migrate
python manage.py seed_demo                               # demo data (DEBUG only)
python manage.py runserver                               # http://localhost:8000/api/v1/docs/
pytest                                                   # needs PostgreSQL; Gemini is mocked
```

## Apps

| App | Contents |
|---|---|
| `accounts` | Custom `User` (email login, `role`), `Team`, cookie JWT authentication, auth endpoints, admin user management |
| `tickets` | `Ticket`, `TicketMessage`, `TicketActivity`, `Category`, `SLAPolicy`, `TicketAIInsight`, `ReplyDraft`; `services.py` (workflows), `selectors.py` (visibility), `seed_demo` command |
| `knowledge_base` | `KnowledgeBaseArticle`, full-text search selectors, article/search/ask endpoints |
| `ai` | `client.py` (Gemini wrapper), `schemas.py` (structured output), `prompts.py`, `services.py` (all AI features) |
| `analytics` | Aggregation services and read-only endpoints |
| `audit` | `AuditLog`, `log_action()` service, admin-only read-only API |
| `core` | Permissions, pagination, throttling, exception handler, security headers, health check |

## Useful commands

```bash
python manage.py seed_demo --reset          # recreate demo tickets/articles
python manage.py createsuperuser            # admin (role=ADMIN), also for /admin/
python manage.py spectacular --file openapi.yml --validate
python manage.py check --deploy             # with production env vars set
pytest tests/test_permissions.py -q         # run one test module
```
