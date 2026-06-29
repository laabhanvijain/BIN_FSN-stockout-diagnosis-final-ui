# Progress Journal

> Chronological, detailed log of everything done on the BIN-FSN Stockout Diagnosis
> project. Newest entries at the top. Every entry records **what** was done,
> **why**, and any **decisions/assumptions** made. Keep this updated as work proceeds.

---

## 2026-06-29 — M10 complete: E2E demo wiring

### What was done
- `infra/docker-compose.yml`: added `backend` (:8000) and `frontend` (:3000) services;
  env overrides for container-to-container hostnames; `depends_on` with health-check gating.
- `infra/Dockerfile.frontend`: fixed port from 5173 → 3000.
- `infra/init_schema.sh`: polls both stores until healthy, applies StarRocks DDL via mysql,
  applies NebulaGraph schema via nebula-console or Python fallback. IF NOT EXISTS = re-runnable.
- `infra/smoke_test.sh`: checks /health, /api/diagnoses (all 4 verdicts), /api/feedback
  (failures_ceased), /api/ask (200 or 503). Exits non-zero on any failure.
- `README.md`: 5-step quick start, demo script, env table, full project layout.

### Decisions
- Container hostnames via env overrides (not hardcoded) — local dev uses localhost defaults.
- `init_schema.sh` fallback to Python — nebula-console not always installed.
- 503 on /ask accepted in smoke test — correct response when API key absent (CI environments).

### Status: committed 2026-06-29

---

## 2026-06-27 — M9 complete: React UI (3 surfaces)

### What was done
- Vite+React scaffold (React 18, Axios 1.7), `/api` proxy to FastAPI backend.
- `api.js`: axios wrappers for all 5 API calls.
- `App.jsx`: tab bar + warehouse filter. `App.css`: full dark theme.
- `DiagnosesTable.jsx`: verdict grid, badge colours, graph signals, Log Rec button.
- `Assistant.jsx`: chat UI, route badge, collapsible citations.
- `FeedbackView.jsx`: lifecycle table, failures delta colouring, → advance button.

### Decisions
- No React Router — tab via `useState` (3 surfaces, no deep URLs).
- Vite proxy handles dev CORS — no env vars or CORS config needed.
- Monolithic `App.css` — correct for demo scale.

### Status: committed 2026-06-27

---

## 2026-06-26 — M8 complete: closed-loop feedback (/feedback)

### What was done
- `backend/services/feedback.py`: `list_recommendations` (with `failures_ceased`),
  `create_recommendation` (captures `failures_before` from live pendency_mv at POST time),
  `advance_status` (lifecycle validation, captures `failures_after` at `executed`,
  sets `resolved_at` at `verified`).
- `backend/routers/feedback.py`: `GET/POST /api/feedback`, `PATCH /api/feedback/{id}/status`.
  Pydantic validates verdict enum and lifecycle target status.
- `backend/main.py`: feedback router registered.

### Decisions
- `failures_before` locked at creation time — live COUNT so baseline is always accurate.
- `failures_after` captured at `executed` — measures real post-action state.
- Lifecycle transitions validated server-side via `VALID_TRANSITIONS` dict.
- `failures_ceased` computed in Python post-query (keeps SQL simple).

### Status: committed 2026-06-26

---

## 2026-06-26 — M7 complete: LLM assistant (POST /ask)

### What was done
- `backend/services/llm.py`: Haiku routing (SQL_ONLY/GRAPH_ONLY/SQL_GRAPH/OUT_OF_SCOPE),
  Sonnet agentic loop (max 8 rounds), `run_sql`/`run_ngql` tools with regex deny-list,
  row cap at 50, citation enforcement via `---CITATIONS---` post-processing.
- `backend/routers/ask.py`: `POST /api/ask`, Pydantic request/response models,
  503 gate for missing API key, question length validation (3–500 chars).
- `backend/main.py`: ask router registered.

### Decisions
- Two-stage (Haiku + Sonnet) — cheap routing before expensive reasoning.
- Regex deny-list blocks DML/DDL; errors returned to model not user for self-correction.
- Max 8 tool rounds hard cap to stay under 10s SLA.
- Citation enforcement: post-process ⚠️ warning if `---CITATIONS---` block absent.

### Status: committed 2026-06-26

---

## 2026-06-26 — M6 complete: graph signal enrichment

### What was done
- `backend/services/graph.py`: 4 additive signals — `picker_concentration` (reverse
  ASSIGNED_TO traversal), `shared_grn` (2-hop FSN→BIN + FSN→GRN), `stocktake_done`
  (BIN→Variance STOCKTAKE edge), `atp_likely_zero` (proxy stub).
- `backend/services/diagnosis.py`: deduplicate (wh,bin) before enrichment; 1 graph
  call per BIN, shared across all FSN rows for that BIN.

### Decisions
- All signals additive; `{}` on failure — graph never blocks SQL verdict.
- Per-signal try/except so one bad query doesn't suppress the others.
- Picker threshold 0.7, ATP as stub — documented for production upgrade.

### Status: committed 2026-06-26

---

## 2026-06-26 — M5 complete: `GET /diagnoses` endpoint

### What was done
- `backend/services/diagnosis.py`: PS CTE verdict SQL (3-CTE), `DiagnosisRow` dataclass,
  `recovery_pct` projection (`orders_impacted / Σ orders_wh × 100`).
- `backend/routers/diagnoses.py`: `GET /api/diagnoses` with `warehouse_id?` + `window_days` (1–30).
- `backend/main.py`: diagnoses router registered.

### Decisions
- PS SQL verbatim — no deviation from spec.
- Warehouse filter in Python so recovery denominator covers full warehouse population.
- `graph_signals: dict = {}` placeholder in M5 — M6 fills without API contract change.

### Status: committed 2026-06-26

---

## 2026-06-25 — M4 complete: ETL sync (StarRocks → NebulaGraph)

### What was done
- `backend/db/starrocks.py`: PyMySQL connection factory (DictCursor).
- `backend/db/nebula.py`: NebulaGraph `ConnectionPool` singleton + `get_session()` context manager.
- `backend/etl/sync.py`: watermark-incremental sync; upserts FSN/BIN/Picker/Order/GRN vertices
  and FAILED_AT/PICKED_FROM/ASSIGNED_TO/RECEIVED_IN/PUTAWAY_TO edges; all errors swallowed.
- `backend/main.py`: migrated to FastAPI `lifespan`; ETL scheduler (1-min) started at startup.

### Decisions
- In-memory watermark (resets on restart) — acceptable for demo; documented for production.
- `IF NOT EXISTS` upserts — idempotent; first run is always a full sync.
- Graph unavailable → warn + return (not raise) — graph signals are additive.

### Status: committed 2026-06-25

---

## 2026-06-25 — M3 complete: dummy data generator (6 scenarios)

### What was done
- `data/generate_dummy_data.py`: 6 ground-truth scenarios (S1 PHANTOM, S2 GENUINE, S3 DUAL,
  S4 PICKER-DRIVEN, S5 SHARED-GRN, S6 NOISE/AMBIGUOUS).
- Fixed `random.seed(42)` for reproducibility; `--clear` flag for safe re-seeding.
- `EXPECTED_VERDICTS` dict inline for accuracy measurement.
- 2 pre-resolved `recommendation_log` rows to demo the closed-loop Feedback UI.

### Decisions
- S4/S5 SQL verdict stays PHANTOM — graph signals are additive enrichments on top.
- Pre-seeded `recommendation_log` rows avoid needing to run the full flow just to show
  the Feedback view in the demo.

### Status: committed 2026-06-25

---

## 2026-06-25 — M2 complete: Schema DDL (StarRocks + NebulaGraph)

### What was done
- `data/schema/starrocks.sql`: `CREATE DATABASE hl_customer_outbound`, then
  `pendency_mv` (DUPLICATE KEY, HASH on wh, replication_num=1) and
  `recommendation_log` (AUTO_INCREMENT PK, lifecycle status, failures_before/after).
- `data/schema/nebula.ngql`: space `stockout`, 6 tags (FSN, BIN, Picker, Order, GRN, Variance),
  6 edge types (FAILED_AT, PICKED_FROM, ASSIGNED_TO, RECEIVED_IN, PUTAWAY_TO, STOCKTAKE),
  tag indexes with immediate `REBUILD TAG INDEX`.

### Decisions
- BIN VID = `wh_id:label` — guarantees cross-warehouse uniqueness.
- DUPLICATE KEY (not UNIQUE) — multiple INF events per triple are all valid rows.
- `grn_id` as a column on `pendency_mv`, not a new StarRocks MV — respects PS guardrail.
- Added `Variance` tag to support the STOCKTAKE closed-loop edge.

### Status: committed 2026-06-25

---

## 2026-06-25 — M1 complete: Docker infra (StarRocks + NebulaGraph)

### What was done
- `infra/docker-compose.yml`: 5 containers on shared `demo-net` bridge network —
  StarRocks FE+BE and NebulaGraph metad/storaged/graphd.
- Ports exposed: StarRocks SQL `:9030`, HTTP `:8030`; NebulaGraph nGQL `:9669`.
- Named volumes for data persistence across restarts.
- Health checks on `starrocks-fe` (`/api/health`) and `nebula-graphd` (`/status`), 15 retries each.
- `infra/Dockerfile.backend`: `python:3.11-slim`, installs requirements, runs uvicorn.
- `infra/Dockerfile.frontend`: `node:20-alpine`, npm install, runs Vite dev server.
- Backend + frontend intentionally omitted from compose — added in M10 when all code is ready.

### Decisions
- Health-check gating: `starrocks-be` depends on FE healthy so BE never starts before FE is ready.
- Backend/frontend Dockerfiles created now so they exist alongside the compose file, even though
  they aren't wired into compose yet.

### Status: committed 2026-06-25

---

## 2026-06-25 — M0 complete: project skeleton

### What was done
- `backend/` Python package: `main.py` (FastAPI app + CORS + /health), `config.py`
  (Pydantic settings for all env vars), `requirements.txt` (all deps pinned).
- Package stubs: `backend/routers/`, `backend/services/`, `backend/db/`, `backend/etl/`.
- `.env.example` documenting all required env vars (StarRocks, NebulaGraph, Anthropic, thresholds).
- Placeholder `.gitkeep` files for `frontend/`, `data/schema/`, `infra/` so git tracks the folders.

### Decisions
- Router registrations commented out in `main.py` — uncommented one per milestone as code is added.
- Thresholds (`PHANTOM_FSN_THRESHOLD=3`, `STOCKOUT_BIN_THRESHOLD=2`) in config so they're
  adjustable without code changes.

### Status: committed 2026-06-25

---

## 2026-06-29 — Project kickoff, research & documentation

### What was done

1. **Read & analyzed the problem statement** (`BIN-FSN Stockout Diagnosis — Intern Briefing Document.pdf`).
   - Extracted the core diagnostic logic (PHANTOM vs GENUINE STOCKOUT), the verdict
     thresholds from the PS validation SQL, the prescribed tech stack, the source
     schema (`hl_customer_outbound.pendency_mv`), the 7-step implementation plan,
     in/out-of-scope guardrails, and the success metrics.

2. **Cloned and studied the WMS context repo** (`Flipkart/assets-project-contexts`).
   - Pulled into `.context-repo/` locally (read-only reference).
   - Read: `README.md`, `SERVICE_REGISTRY.md`, `AGENTS.md`, `FLOW_CATALOG.md`, and
     the `DOMAIN_OVERVIEW.md` for picking, inventory, and inv-audit services.
   - Outcome: understood how INF/IRT, pickers, GRN/inbound, ATP, and stocktake/variance
     mechanics actually work — the basis for extending the FSN x BIN core into an
     e2e root-cause solution.

3. **Confirmed scope with the user** (3 decisions):
   - Build a **full working e2e demo** (not just docs).
   - Extend the PS with **graph multi-hop signals** (picker overlap, shared inbound
     GRN batch, IRT/stocktake feedback).
   - Follow the **PS stack exactly** (FastAPI + React + NebulaGraph + StarRocks, Dockerized).

4. **Authored documentation**:
   - `explanation/context-repository.md` — what the WMS context repo is and why it matters.
   - `design/design-doc.md` — detailed design with decisions DD-1..DD-9.
   - `design/milestones.md` — stepwise milestone plan M0..M10.
   - `docs/` structure (this journal + HLD + LLD scaffolds).

### Why

- The PS only correlates FSN x BIN. To deliver a compelling, action-oriented demo,
  we ground an extended root-cause engine in real WMS behavior documented in the
  context repo. Documenting decisions up front keeps the build auditable.

### Decisions / assumptions made

- INF event isolation: assume `irt_ticket_id IS NOT NULL` until leads confirm the
  exact `irt_ticket_type` enum value.
- `grn_id` will be added as a column on the **dummy** `pendency_mv` table only
  (not a new StarRocks MV — respects the PS guardrail).
- Existing Java/Maven archetype left untouched; demo uses the PS Python+JS stack.

### Status

- Phase: **Planning & documentation complete.** Awaiting go-ahead to start M0/M1.

### Next steps

- M0: project skeleton (`backend/`, `frontend/`, `data/`, `infra/`).
- M1: Docker Compose for StarRocks + NebulaGraph.

---

## 2026-06-29 — M0–M9 built: full project skeleton through React UI

### What was done

- **M0 Skeleton**: `backend/`, `frontend/`, `data/`, `infra/` folder structure created.
  `requirements.txt`, `.env.example`, `backend/main.py`, `backend/config.py`.
- **M1 Infra**: `infra/docker-compose.yml` (StarRocks FE+BE, NebulaGraph metad/storaged/graphd,
  backend, frontend services). `infra/Dockerfile.backend`, `infra/Dockerfile.frontend`.
- **M2 Schema**: `data/schema/starrocks.sql` (pendency_mv + recommendation_log DDL).
  `data/schema/nebula.ngql` (space, tags FSN/BIN/Picker/Order/GRN/Variance, edges, indexes).
- **M3 Dummy data**: `data/generate_dummy_data.py` — 6 ground-truth scenarios (PHANTOM,
  GENUINE_STOCKOUT, DUAL, PICKER-DRIVEN, SHARED-GRN, NOISE) + 2 resolved recommendation_log rows.
- **M4 ETL**: `backend/etl/sync.py` — APScheduler 60s cron, watermark-incremental,
  idempotent vertex/edge upserts into NebulaGraph.
- **M5 Diagnoses API**: `backend/routers/diagnoses.py` + `backend/services/diagnosis.py` —
  PS verdict SQL (PHANTOM/GENUINE_STOCKOUT/DUAL/AMBIGUOUS), configurable thresholds, recovery projection.
- **M6 Graph signals**: `backend/services/graph.py` — picker_concentration, shared_grn,
  stocktake_done nGQL queries; graceful fallback if graph unavailable.
- **M7 LLM assistant**: `backend/routers/ask.py` + `backend/services/llm.py` — Haiku route,
  Sonnet reason, run_sql/run_ngql tools, mandatory citation blocks, query whitelist.
- **M8 Feedback**: `backend/routers/feedback.py` + `backend/services/feedback.py` —
  recommendation_log CRUD, failures_ceased computation.
- **M9 Frontend**: React/Vite app (`frontend/src/`) — `App.jsx`, `App.css`, `api.js`,
  `DiagnosesTable.jsx`, `Assistant.jsx`, `FeedbackView.jsx`. Axios, tab navigation,
  verdict badges, graph signal display, citation expandable, status-advance buttons.
- **Updated `.gitignore`**: Python, Node, .env, and all internal planning folders.

### Decisions made during the build

- Haiku-first routing: cheap classification before expensive Sonnet reasoning.
- Graph signals swallowed on failure (additive, not blocking) so SQL verdict still works.
- Picker concentration threshold: 70% from one picker -> flag as picker-driven.
- In-memory ETL watermark (resets on restart); acceptable for demo; noted for production upgrade.

### Status

All code written. Awaiting: `docker compose up` (M10 demo wiring), schema init, data seed, smoke test.

---

<!-- TEMPLATE for new entries — copy below and fill in -->
<!--
## YYYY-MM-DD — <short title>

### What was done
-

### Why
-

### Decisions / assumptions made
-

### Files changed
-

### Status / Next steps
-
-->
