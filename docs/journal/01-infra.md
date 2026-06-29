# 01 · Infrastructure (Docker / StarRocks / NebulaGraph)

> Notes on local infra setup. Newest dated subsection at top.
> Milestones: M1 (infra), part of M10 (demo wiring).

_Status: done (M1, committed 2026-06-25)._

## 2026-06-25 — Docker Compose for StarRocks + NebulaGraph

- `infra/docker-compose.yml`: 5 containers on `demo-net` bridge network.
- StarRocks SQL on `:9030`, HTTP on `:8030`; NebulaGraph nGQL on `:9669`.
- Named volumes: `sr-fe-data`, `sr-be-data`, `nebula-meta`, `nebula-storage`.
- Health checks: `starrocks-fe` (`/api/health`), `nebula-graphd` (`/status`) — 15 retries each.
- `Dockerfile.backend`: `python:3.11-slim`. `Dockerfile.frontend`: `node:20-alpine`.
- Backend + frontend not yet wired into compose (comes in M10).

---

## 2026-06-29 — M10 complete: full stack wired + init scripts + smoke test

### What was done

**`infra/docker-compose.yml`** (updated)
- Added `backend` service: builds from `infra/Dockerfile.backend`, exposes `:8000`,
  reads `.env` for API keys, env overrides `STARROCKS_HOST=starrocks-fe` and
  `NEBULA_HOST=nebula-graphd` so containers resolve each other by name.
- Added `frontend` service: builds from `infra/Dockerfile.frontend`, exposes `:3000`.
- Both depend on the data store health checks so they start after StarRocks FE and
  NebulaGraph graphd are healthy.
- Fixed `Dockerfile.frontend` port: was 5173, corrected to 3000 (matches vite.config.js).

**`infra/init_schema.sh`**
- Polls StarRocks FE (mysql CLI) and NebulaGraph graphd (curl `/status`) until healthy.
- Applies `data/schema/starrocks.sql` via mysql client.
- Applies `data/schema/nebula.ngql` via `nebula-console` if installed, or falls back to
  Python nebula3 library (splits on `;` and executes each statement).
- All DDL uses `IF NOT EXISTS` — safe to re-run.

**`infra/smoke_test.sh`**
- Checks: `GET /health`, `GET /api/diagnoses` (expects > 0 rows + all 4 verdicts present),
  `GET /api/feedback` (expects pre-seeded rows + at least 1 `failures_ceased` value),
  `POST /api/ask` (200 with key, 503 without — both acceptable in CI).
- Exits non-zero if any check fails.

**`README.md`**
- Full quick-start (5 steps), demo script (what to click and ask), env var table,
  project layout tree, tech stack table.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| `STARROCKS_HOST`/`NEBULA_HOST` env overrides | In compose environment block | Lets backend config.py defaults work locally (`localhost`) while Docker uses service names |
| `depends_on` with health checks | service_healthy condition | Backend never starts before stores accept connections |
| `init_schema.sh` fallback to Python | nebula-console or Python | nebula-console may not be installed; Python client is in requirements.txt |
| `smoke_test.sh` accepts 503 for /ask | Not a failure | CI environments won't have ANTHROPIC_API_KEY; 503 is the correct configured response |

### Status: committed 2026-06-29

<!-- ## YYYY-MM-DD — <what happened> -->
