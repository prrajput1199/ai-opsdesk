# AI OpsDesk — Frontend (React + TypeScript + Vite)

See the [root README](../README.md) for full setup and deployment.

```bash
npm install
npm run dev          # http://localhost:5173 (proxies /api to http://localhost:8000)
npm test             # Vitest + Testing Library
npm run typecheck    # tsc, strict mode
npm run build        # production build in dist/
```

## Structure

| Path | Purpose |
|---|---|
| `src/lib/api.ts` | Axios instance: cookies (`withCredentials`), CSRF header, automatic token refresh on 401, error formatting |
| `src/api/` | TanStack Query hooks for each API area (`auth`, `tickets`, `kb`, `analytics`, `admin`) |
| `src/context/AuthContext.tsx` | Current user + role helpers |
| `src/components/ui/` | Small shadcn-style component library (Radix primitives, Tailwind) |
| `src/components/layout/` | App shell with role-based sidebar, route guards |
| `src/components/tickets/` | Badges, filters, table, conversation, reply composer, AI panel, controls |
| `src/components/analytics/` | Recharts charts, date range picker |
| `src/pages/` | One component per screen (lazy-loaded) |
| `src/test/` | Unit and component tests |

The UI hides actions a role can't perform, but **the API enforces every rule**; the frontend never relies on hiding for security.

## Environment

`VITE_API_BASE_URL` (default `/api/v1`) and `VITE_PROXY_TARGET` (dev only). See `.env.example`.

For Vercel, edit `vercel.json` so `/api/*` rewrites to your backend. For Docker, `nginx.conf` proxies `/api` to the `backend` service.
