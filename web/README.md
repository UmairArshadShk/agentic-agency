# Web UI

Bare chat UI for the agency: project list, streaming chat, and Approve / Request changes at gates.
Next.js (App Router, TypeScript) with pnpm. It talks to the API at `NEXT_PUBLIC_API_URL`
(default `http://127.0.0.1:8000`).

```
make api        # terminal 1: the API on 127.0.0.1:8000
make web        # terminal 2: this UI on http://localhost:3001
make web-check  # lint, typecheck, unit tests, build
make web-e2e    # Playwright against the real API and UI
```

There is no login in M0 (see `docs/DECISIONS.md`), so run both on localhost only.
