# infra/ — Code Walkthrough (M1 + M10)

> Source: `infra/docker-compose.yml`, `infra/Dockerfile.backend`, `infra/Dockerfile.frontend`,
> `infra/init_schema.sh`, `infra/smoke_test.sh`
> Milestones: M1 (data stores) · M10 (full stack + scripts) · Last updated: 2026-06-29

## What it does

One `docker compose up --build` starts the full 7-container demo stack. Two helper
scripts handle schema initialisation and E2E smoke testing.

---

## `docker-compose.yml` — service map

```
demo-net (bridge)
├── starrocks-fe     :9030 (SQL), :8030 (HTTP)
├── starrocks-be     (internal)
├── nebula-metad     (internal :9559)
├── nebula-storaged  (internal :9779)
├── nebula-graphd    :9669 (nGQL)
├── backend          :8000 (FastAPI)
└── frontend         :3000 (Vite dev)
```

### Startup order (depends_on with health checks)

```
nebula-metad
  └── nebula-storaged
        └── nebula-graphd (healthy) ──┐
starrocks-fe (healthy) ───────────────┤
  └── starrocks-be                    ├── backend
                                      │     └── frontend
```

Backend only starts after StarRocks FE and NebulaGraph graphd pass their health checks.
Frontend only starts after backend is up.

### Container-to-container hostname resolution

```yaml
backend:
  environment:
    - STARROCKS_HOST=starrocks-fe    # overrides config.py default of "localhost"
    - NEBULA_HOST=nebula-graphd
```

`backend/config.py` defaults to `localhost` for local development. When running in
Docker, the compose environment block overrides these to the service hostnames.
No code change needed between local dev and Docker.

---

## `infra/init_schema.sh`

```bash
wait_starrocks  # polls mysql CLI until connection succeeds (max 3 min)
wait_nebula     # polls curl /status until 200 (max 3 min)
apply_starrocks # mysql < data/schema/starrocks.sql
apply_nebula    # nebula-console -f nebula.ngql  OR  python3 fallback
```

The Python fallback splits `nebula.ngql` on `;` and executes each statement via
the nebula3 library — handles the case where `nebula-console` isn't installed.

All DDL uses `IF NOT EXISTS` — running the script twice is safe.

---

## `infra/smoke_test.sh`

Checks five things in order:

| Check | Endpoint | Pass condition |
|-------|----------|---------------|
| Health | `GET /health` | `{"status":"ok"}` |
| Diagnoses has rows | `GET /api/diagnoses` | count > 0 |
| All 4 verdicts present | same response | PHANTOM, GENUINE, DUAL, AMBIGUOUS all appear |
| Feedback rows exist | `GET /api/feedback` | count > 0 |
| failures_ceased computed | same response | ≥ 1 verified row with non-null failures_ceased |
| Ask endpoint reachable | `POST /api/ask` | 200 (with key) or 503 (without key) |

Exits with code 1 if any check fails. Designed to run in CI without an LLM key.

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Env override for hostnames | `environment:` block | Local dev uses `localhost`; Docker uses service names; zero code change |
| `depends_on: service_healthy` | Health-check gating | Backend must not start before stores accept connections |
| `restart: on-failure` on backend | Yes | Backend may start before stores fully accept queries; one retry is enough |
| `init_schema.sh` dual-path | nebula-console + Python | nebula-console requires separate install; Python client is already in requirements.txt |
| Smoke test accepts 503 on /ask | Not a failure | CI has no ANTHROPIC_API_KEY; 503 is the documented correct response |
| Frontend port 3000 | Changed from 5173 | Matches `vite.config.js` server.port; avoids port confusion |
