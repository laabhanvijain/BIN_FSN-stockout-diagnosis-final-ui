# BIN-FSN Stockout Diagnosis

> Automated root-cause engine for warehouse pick failures (INF events).
> Diagnoses **PHANTOM INVENTORY** vs **GENUINE STOCKOUT** in minutes instead of days,
> enriched with multi-hop graph signals and answered by a cited LLM assistant.

---

## What it does

Store managers see a ranked table of INF clusters, each labelled with a verdict:

| Verdict | Meaning | Recommended action |
|---------|---------|-------------------|
| **PHANTOM_INVENTORY** | Many distinct FSNs fail in one BIN — item is listed but physically missing | Stocktake the BIN |
| **GENUINE_STOCKOUT** | One FSN fails across many BINs — item truly depleted | Replenish |
| **DUAL** | Both signals active simultaneously | Stocktake + replenish |
| **AMBIGUOUS** | Neither threshold crossed — isolated noise | Investigate |

The **LLM assistant** (Ollama with llama3.1:8b by default) answers natural-language
questions over live data with:
- **Dynamic graph signal queries** — picks relevant signals based on the question
- **Tool-calling** with query_starrocks and query_nebulagraph
- **Deterministic fallbacks** for weaker models (auto-bootstrap, SQL extraction, hallucination blocking)
- **Mandatory citations** — every claim cited with query results
- **Depth modes** — FAST (10s) or THOROUGH (30s) investigation budgets

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| Analytics store | StarRocks 3.2 (MySQL protocol) |
| Graph store | NebulaGraph 3.8 |
| LLM | Ollama (default: llama3.1:8b) - OpenAI-compatible API |
| Frontend | React 18, Vite 5, Axios |
| Infra | Docker Compose |

---

## Quick start

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.11+ (for data seeding, outside Docker)
- `mysql` CLI client (for schema init)
- **Ollama** installed and running locally ([ollama.com](https://ollama.com))
  ```bash
  ollama pull llama3.1:8b
  ollama serve
  ```

### 1. Clone and configure

```bash
git clone <repo-url>
cd BIN_FSN-stockout-diagnosis
cp .env.example .env
# Edit .env if needed (defaults work with local Ollama)
```

### 2. Start all services

```bash
docker compose -f infra/docker-compose.yml up --build
```

Wait until you see StarRocks FE health and NebulaGraph graphd health pass
(~60–90 seconds on first run while images download).

### 3. Initialise schema

In a second terminal:

```bash
bash infra/init_schema.sh
```

This waits for both stores to be ready, then applies the StarRocks DDL
(`data/schema/starrocks.sql`) and NebulaGraph schema (`data/schema/nebula.ngql`).

### 4. Seed demo data

```bash
pip install pymysql   # if not already installed
python data/generate_dummy_data.py --clear
```

Seeds 6 ground-truth scenarios (PHANTOM, GENUINE, DUAL, PICKER-DRIVEN, SHARED-GRN, NOISE)
and 2 pre-resolved feedback rows.

### 6. (Optional) Start continuous generator

```bash
python data/data_generator.py --interval 3
```

Generates live INF events (repeat/adjust/new_bin/new_fsn rotation). Stop with Ctrl+C.

### 5. Open the UI

```
http://localhost:3000
```

### 6. Smoke test

```bash
bash infra/smoke_test.sh
```

---

## Demo script (what to show)

### Tab 1 — Diagnoses

1. Warehouse ID defaults to `WH-BLR-001`. Click **↻ Refresh**.
2. Point to `BIN-PHANTOM-A` — **Phantom Inventory** badge, 5 distinct FSNs, no graph signals.
3. Point to `BIN-PICKER-A` — also Phantom verdict, but graph signal shows **PKR-BAD (100%)**.
   Explain: same SQL verdict, different root cause revealed by the graph.
4. Point to `BIN-GRN-A` — Phantom verdict + **Shared GRN: GRN-SHARED-999** (bad inbound batch).
5. Point to `FSN-S2-001` rows — **Genuine Stockout**, appears in 3 BINs, ATP likely 0.
6. Click **Log Rec** on any row → creates a recommendation in the Feedback tab.

### Tab 2 — Assistant

Ask these questions to demo the LLM:
- *"Why is BIN-PICKER-A failing so often?"* — triggers verdict + inventory queries
- *"Which BIN has the most distinct FSN failures?"* — SQL aggregation
- *"Is FSN-S2-001 genuinely out of stock?"* — AMBIGUOUS investigation (inventory + inbound)
- *"Why is BIN-PHANTOM-A failing?"* — auto-bootstrap verdict counts + inventory

The LLM uses **depth_mode**:
- **FAST** (10s budget) — quick verdict + one upstream check
- **THOROUGH** (30s budget) — complete AMBIGUOUS investigation

### Tab 3 — Feedback

1. The two pre-seeded rows (`BIN-PHANTOM-A` and `BIN-GENUINE-A`) show `status: verified`
   and `failures_ceased: 10` and `8` respectively — proof the loop closed.
2. Advance a freshly-logged recommendation through `acknowledged → executed → verified`
   to show the live delta computation.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STARROCKS_HOST` | `localhost` | StarRocks FE host |
| `STARROCKS_PORT` | `9030` | StarRocks SQL port |
| `NEBULA_HOST` | `localhost` | NebulaGraph graphd host |
| `NEBULA_PORT` | `9669` | NebulaGraph nGQL port |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible API |
| `LLM_API_KEY` | `ollama` | API key (any value for local Ollama) |
| `LLM_MODEL` | `llama3.1:8b` | Model name (must be pulled in Ollama) |
| `ASK_TOTAL_TIMEOUT_MS` | `10000` | FAST mode timeout (10s) |
| `ASK_THOROUGH_TIMEOUT_MS` | `30000` | THOROUGH mode timeout (30s) |
| `ASK_MAX_ITERATIONS` | `12` | Max LLM tool loop iterations |
| `PHANTOM_FSN_THRESHOLD` | `3` | distinct_fsns threshold for PHANTOM verdict |
| `STOCKOUT_BIN_THRESHOLD` | `2` | distinct_bins threshold for GENUINE_STOCKOUT |
| `DIAGNOSIS_WINDOW_DAYS` | `1` | Default lookback window for verdicts |

---

## Project layout

```
BIN_FSN-stockout-diagnosis/
├── backend/
│   ├── main.py              FastAPI app (lifespan: ETL scheduler + NebulaGraph pool)
│   ├── config.py            Pydantic settings from .env
│   ├── db/
│   │   ├── starrocks.py     PyMySQL connection factory
│   │   └── nebula.py        NebulaGraph ConnectionPool singleton
│   ├── etl/
│   │   └── sync.py          1-min watermark-incremental StarRocks→Graph ETL
│   ├── routers/
│   │   ├── diagnoses.py     GET /api/diagnoses
│   │   ├── ask.py           POST /api/ask
│   │   └── feedback.py      GET/POST/PATCH /api/feedback
│   └── services/
│       ├── diagnosis.py     PS verdict SQL + recovery projection
│       ├── graph.py         Graph query helpers (used by agent)
│       ├── llm.py           Ollama client wrapper (OpenAI-compatible)
│       ├── agent.py         Tool-calling loop + deterministic fallbacks
│       ├── guards.py        SQL/nGQL validation
│       ├── prompts.py       System prompts + AMBIGUOUS playbook
│       └── feedback.py      recommendation_log CRUD + failures_ceased
├── frontend/
│   └── src/
│       ├── App.jsx          Tab shell + warehouse filter
│       ├── DiagnosesTable.jsx
│       ├── Assistant.jsx
│       └── FeedbackView.jsx
├── data/
│   ├── schema/
│   │   ├── starrocks.sql    DDL for pendency_mv + recommendation_log
│   │   └── nebula.ngql      Space, tags, edges, indexes
│   ├── generate_dummy_data.py  6 ground-truth scenarios
│   └── data_generator.py   Continuous event generator (optional)
└── infra/
    ├── docker-compose.yml   Full 7-service stack
    ├── Dockerfile.backend
    ├── Dockerfile.frontend
    ├── init_schema.sh       Wait + apply DDL
    └── smoke_test.sh        E2E health + verdict + feedback checks
```
