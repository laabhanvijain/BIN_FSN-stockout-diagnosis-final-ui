# AGENTS.md — Project Source of Truth

> The single file to read first. It holds project context, the milestone roadmap
> (with checkboxes), documentation health, and the "where we left off" pointer.
> The `.Codex/commands/` rituals (`/sod`, `/eod`, `/milestone-complete`, `/docs-review`)
> all read and update this file.

---

## 1. What This Project Is

**BIN-FSN Stockout Diagnosis** — an automated web UI + Graph/LLM assistant that
diagnoses warehouse pick failures (INF events) into actionable root causes
(**PHANTOM INVENTORY** vs **GENUINE STOCKOUT**), reducing diagnosis from 3-5 days
to minutes. See [design/design-doc.md](design/design-doc.md) for full detail.

- **Stack**: FastAPI (Python) · React · StarRocks · NebulaGraph · Ollama (llama3.1:8b) · Docker.
- **Core logic**: many FSNs failing in one BIN -> PHANTOM (stocktake); one FSN failing
  across many BINs -> GENUINE_STOCKOUT (replenish).
- **E2E extension**: graph multi-hop signals (picker overlap, shared GRN batch,
  IRT/stocktake feedback, ATP cross-check) grounded in the WMS context repo.

---

## 2. Key References

| Topic | File |
|-------|------|
| WMS context repo explained | [explanation/context-repository.md](explanation/context-repository.md) |
| Design decisions | [design/design-doc.md](design/design-doc.md) |
| Milestone plan (with tickboxes) | [design/milestones.md](design/milestones.md) |
| Progress journal | [docs/journal/](docs/journal/) |
| HLD | [docs/deliverables/HLD/](docs/deliverables/HLD/) |
| LLD | [docs/deliverables/LLD/](docs/deliverables/LLD/) |
| Code walkthroughs | [docs/code-walkthroughs/](docs/code-walkthroughs/) |

---

## 3. Guardrails (from the PS)

- Read only `hl_customer_outbound.pendency_mv`; **no new StarRocks MVs**.
- No Slack/email/push; no automated stocktake execution; no ML forecasting; no LLM fine-tuning.
- Verdict accuracy >= 70% vs analyst; e2e latency < 10s; **every** assistant claim cited.

---

## 4. Documentation Tracks

| Track | Where | Purpose |
|-------|-------|---------|
| **Journal** | `docs/journal/*.md` | Chronological + topic-specific running notes |
| **HLD** | `docs/deliverables/HLD/*.md` | Architecture-level deliverable |
| **LLD** | `docs/deliverables/LLD/*.md` | Implementation-level deliverable |
| **Code walkthroughs** | `docs/code-walkthroughs/*.md` | Per-module explanation of what the code does (written after coding) |

**Rule**: after writing any code, update the matching code-walkthrough file and the
relevant HLD/LLD subfile, and add a journal entry.

---

## 5. Current Status

- **Phase**: **ALL MILESTONES COMPLETE (M0–M10)**. Migrated to Ollama (M11).
- **Prerequisites**: Install Ollama ([ollama.com](https://ollama.com)) → `ollama pull llama3.1:8b` → `ollama serve`
- **To run**: `cp .env.example .env` → `docker compose -f infra/docker-compose.yml up --build` → `bash infra/init_schema.sh` → `python data/generate_dummy_data.py --clear` → open http://localhost:3000
- **Optional**: `python data/data_generator.py` for continuous event stream
- **Smoke test**: `bash infra/smoke_test.sh`

---

## 6. Doc Health Snapshot

| Doc area | Status |
|----------|--------|
| Journal | M0–M10 complete (progress-log, 01-infra, 02-data-and-schema, 03-etl, 04-backend-api, 05-graph-signals, 06-llm-assistant, 07-frontend, 09-decisions) |
| HLD | All sections written (01-context, 02-architecture, 03-data-flows, 04-e2e-extension, 05-technical-decisions, 06-quality-attributes) |
| LLD | All sections written (01–09 complete) |
| Code walkthroughs | M1–M10 all written (9 files covering every module) |
| README | Full quick-start, demo script, env table, project layout |

---

## 7. Milestone Roadmap

> Mirror of [design/milestones.md](design/milestones.md). Tick code + journal + HLD + LLD
> for each milestone. `/milestone-complete N` updates this section.

- [x] **M0 · Foundations & repo setup**
  - [x] code · [x] journal · [x] HLD · [x] LLD
- [x] **M1 · Local infra (Docker: StarRocks + NebulaGraph)**
  - [x] code · [x] journal · [x] HLD · [x] LLD
- [x] **M2 · Schema & stores**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M3 · Dummy data generation**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M4 · ETL StarRocks -> NebulaGraph (1-min)**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M5 · Diagnoses API (GET /diagnoses)**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M6 · Graph signal enrichment**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M7 · LLM assistant (POST /ask)**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M8 · Closed-loop feedback (/feedback)**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M9 · React UI (3 surfaces)**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough
- [x] **M10 · E2E demo integration**
  - [x] code · [x] journal · [x] HLD · [x] LLD · [x] code-walkthrough · [x] README

---

## 8. Change Log

| Date | Change |
|------|--------|
| 2026-06-29 | AGENTS.md created; docs structure + command rituals established |
| 2026-06-25 | M0 complete — project skeleton committed |
| 2026-06-25 | M1 complete — Docker Compose + Dockerfiles added |
| 2026-06-25 | M2 complete — StarRocks DDL + NebulaGraph schema committed |
| 2026-06-25 | M3 complete — dummy data generator (6 scenarios + 2 rec_log rows) |
| 2026-06-25 | M4 complete — ETL sync (StarRocks → NebulaGraph, 1-min APScheduler) |
| 2026-06-26 | M5 complete — GET /diagnoses (PS verdict SQL, recovery projection) |
| 2026-06-26 | M6 complete — graph signal enrichment (picker, shared GRN, stocktake, ATP proxy) |
| 2026-06-26 | M7 complete — LLM assistant POST /ask (original: Haiku + Sonnet) |
| 2026-06-29 | M11 complete — Migrated to Ollama (llama3.1:8b, dynamic graph signals, continuous generator) |
| 2026-06-26 | M8 complete — closed-loop feedback (GET/POST/PATCH /feedback, failures_ceased) |
| 2026-06-27 | M9 complete — React UI (DiagnosesTable, Assistant, FeedbackView, dark theme) |
| 2026-06-29 | M10 complete — E2E demo wiring (full compose stack, init_schema.sh, smoke_test.sh, README) |
