# Overall Project Flow

## One-Paragraph Summary

BIN-FSN Stockout Diagnosis is a web application that helps warehouse/store
operators understand why pick failures are happening. When a picker cannot find
an item in a bin, the event is treated as an INF failure. The system reads those
failures from StarRocks, classifies them using deterministic rules, copies useful
relationships into NebulaGraph, lets an LLM assistant investigate the data with
citations, and shows everything in a React UI.

## The Problem In Simple Words

Imagine a warehouse shelf/bin says it contains an item, but the picker cannot
find it. There are two common reasons:

1. The item is missing only from that physical bin.
   - This is likely phantom inventory.
   - The system thinks stock exists, but physically it is not there.
   - The action is usually stocktake the bin.

2. The same item is missing from many bins.
   - This is likely a genuine stockout.
   - The warehouse really does not have enough of that item.
   - The action is usually replenish the item.

This project automates that investigation.

## Main Concepts

| Term | Simple Meaning |
|---|---|
| FSN | Product/item identifier. Think "which product?" |
| BIN | Physical warehouse location. Think "which shelf/slot?" |
| INF | Item Not Found event. A picker tried to pick but could not find the item. |
| IRT | Inventory Resolution Ticket created after an INF-like problem. |
| Phantom inventory | System says stock exists, but physically it is missing/misplaced. |
| Genuine stockout | The item is actually depleted across the facility. |
| Verdict | The system's root-cause label for a failure cluster. |
| Graph signal | Extra evidence from relationships, such as picker overlap or shared GRN. |
| GRN | Goods Receipt Note / inbound batch identifier. |

## High-Level Architecture

```text
React UI
  |
  | HTTP requests to /api/*
  v
FastAPI backend
  |
  | SQL queries
  v
StarRocks
  |
  | 1-minute ETL sync
  v
NebulaGraph

FastAPI backend also calls:
  - Ollama LLM for assistant answers
  - StarRocks tools for SQL evidence
  - NebulaGraph tools for graph evidence
```

## What Each Major Part Does

| Part | Folder/File | Responsibility |
|---|---|---|
| Frontend app | `frontend/src/` | Shows diagnoses, assistant, and feedback screens. |
| Backend app | `backend/main.py` | Starts FastAPI, routers, CORS, NebulaGraph pool, and ETL scheduler. |
| API routers | `backend/routers/` | Define HTTP endpoints such as `/api/diagnoses`, `/api/ask`, `/api/feedback`. |
| Business services | `backend/services/` | Contain diagnosis logic, graph signals, LLM agent, feedback logic. |
| StarRocks DB client | `backend/db/starrocks.py` | Opens SQL connections to StarRocks. |
| NebulaGraph client | `backend/db/nebula.py` | Opens graph sessions to NebulaGraph. |
| ETL sync | `backend/etl/sync.py` | Copies recent INF rows from StarRocks into NebulaGraph. |
| Schemas | `data/schema/` | Defines SQL tables and graph tags/edges. |
| Demo data | `data/generate_dummy_data.py` | Seeds known scenarios for demo and testing. |
| Infra | `infra/` | Docker Compose, Dockerfiles, schema init, smoke test. |
| Docs | `docs/`, `design/`, `AGENTS.md` | Explain architecture, decisions, progress, and code behavior. |

## Runtime Flow 1: Loading The Diagnoses Table

This is the most important basic flow.

```text
User opens React UI
  -> App.jsx renders the Diagnoses tab
  -> DiagnosesTable.jsx calls fetchDiagnoses()
  -> api.js sends GET /api/diagnoses
  -> backend/routers/diagnoses.py receives the request
  -> backend/services/diagnosis.py runs SQL against StarRocks
  -> StarRocks returns grouped INF failure counts
  -> diagnosis.py applies verdict rules
  -> diagnosis.py optionally attaches graph signals
  -> FastAPI returns JSON
  -> React renders rows and verdict badges
```

The core rule is:

```text
many FSNs failing in one BIN -> PHANTOM_INVENTORY
same FSN failing across many BINs -> GENUINE_STOCKOUT
both patterns at once -> DUAL
neither pattern strong enough -> AMBIGUOUS
```

## Runtime Flow 2: Keeping The Graph Updated

The graph is not the source of truth. StarRocks is the source for raw INF rows.
The graph is a second representation that makes relationship questions easier.

```text
FastAPI starts
  -> backend/main.py creates APScheduler
  -> scheduler runs backend/etl/sync.py every 1 minute
  -> sync.py reads recent INF rows from StarRocks
  -> sync.py creates/upserts graph vertices:
       FSN, BIN, Picker, Order, GRN
  -> sync.py creates/upserts graph edges:
       FAILED_AT, PICKED_FROM, ASSIGNED_TO, RECEIVED_IN, PUTAWAY_TO
  -> NebulaGraph becomes queryable for multi-hop signals
```

Why graph matters:

- SQL is good at counts.
- Graph is good at relationships.
- Example graph question: "Are these failures connected to the same picker or
  the same inbound batch?"

## Runtime Flow 3: Asking The Assistant

```text
User types question in Assistant tab
  -> Assistant.jsx calls askQuestion()
  -> api.js sends POST /api/ask
  -> backend/routers/ask.py validates request body
  -> backend/services/agent.py starts a tool-calling loop
  -> agent may query StarRocks for SQL evidence
  -> agent may query NebulaGraph for graph evidence
  -> guards.py validates SQL/nGQL before execution
  -> prompts.py instructs the model to cite claims
  -> llm.py calls Ollama through OpenAI-compatible API
  -> agent.py returns answer plus citations
  -> React displays answer and evidence
```

The assistant should not invent warehouse facts. Its answers are supposed to be
grounded in query results.

## Runtime Flow 4: Logging Feedback

```text
User clicks Log Rec from a diagnosis row
  -> React calls createRecommendation()
  -> api.js sends POST /api/feedback
  -> backend/routers/feedback.py validates body
  -> backend/services/feedback.py inserts into recommendation_log
  -> FeedbackView.jsx displays the new recommendation

Later:
  -> User advances status
  -> PATCH /api/feedback/{id}/status
  -> backend computes whether failures decreased or ceased
  -> UI shows the feedback outcome
```

This creates the closed loop:

```text
diagnosis -> recommended action -> operation performed -> outcome measured
```

## Data Flow Summary

```text
Dummy generator / live WMS-like events
  -> StarRocks pendency_mv
  -> Diagnoses API computes verdicts
  -> React table shows verdicts

StarRocks pendency_mv
  -> ETL sync
  -> NebulaGraph
  -> graph signals and assistant evidence

Diagnosis row
  -> recommendation_log
  -> Feedback UI
  -> failures_before/failures_after comparison
```

## State Storage

| State | Stored In |
|---|---|
| Raw/demo INF events | StarRocks table `hl_customer_outbound.pendency_mv` |
| Recommendations and feedback | StarRocks table `recommendation_log` |
| Relationship graph | NebulaGraph space `stockout` |
| UI local state | React component state |
| LLM model | Ollama local runtime |
| Environment config | `.env` and `backend/config.py` |

## Most Critical Files

If you only had time to read ten files, read these:

1. `AGENTS.md`
2. `README.md`
3. `data/schema/starrocks.sql`
4. `data/schema/nebula.ngql`
5. `backend/main.py`
6. `backend/services/diagnosis.py`
7. `backend/etl/sync.py`
8. `backend/services/graph.py`
9. `backend/services/agent.py`
10. `frontend/src/App.jsx`

## Beginner Mental Model

Think of the project as four layers:

1. Data layer
   - Stores facts.
   - StarRocks stores rows.
   - NebulaGraph stores relationships.

2. Backend layer
   - Reads facts.
   - Applies rules.
   - Calls tools.
   - Returns JSON.

3. Intelligence layer
   - Deterministic diagnosis first.
   - Graph signals second.
   - LLM assistant last.

4. Frontend layer
   - Shows the result.
   - Lets users ask questions.
   - Lets users log outcomes.

Do not start by trying to understand the LLM. First understand the data and the
deterministic diagnosis rule. The LLM only makes sense after that.
