# Low-Level Design (LLD) — BIN-FSN Stockout Diagnosis

> Status: Draft v1 · Last updated: 2026-06-29
> Related: [../HLD/HLD.md](../HLD/HLD.md) · [../../../design/design-doc.md](../../../design/design-doc.md)

Implementation-level detail: exact schemas, endpoint contracts, module layout,
algorithms, and queries. This document is filled in progressively as each
milestone is built. Sections marked **(planned)** are not yet implemented.

---

## 1. Repository Layout (planned)

```
BIN-FSN-stockout-diagnosis/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── requirements.txt
│   ├── routers/
│   │   ├── diagnoses.py        # GET /diagnoses
│   │   ├── ask.py              # POST /ask
│   │   └── feedback.py         # GET/POST /feedback
│   ├── services/
│   │   ├── diagnosis.py        # verdict SQL + scoring
│   │   ├── graph.py            # nGQL signal queries
│   │   └── llm.py              # LLM tool-agent
│   ├── etl/
│   │   └── sync.py             # StarRocks -> NebulaGraph, 1-min
│   └── db/
│       ├── starrocks.py        # connection + queries
│       └── nebula.py           # connection + nGQL
├── frontend/                   # React app (Diagnoses / Assistant / Feedback)
├── data/
│   ├── schema/                 # DDL (SQL + nGQL)
│   └── generate_dummy_data.py
└── infra/
    └── docker-compose.yml
```

---

## 2. Data Schemas

### 2.1 StarRocks — `hl_customer_outbound.pendency_mv` (read-only source)

| Column | Type | Notes |
|--------|------|-------|
| `reservation_warehouse_id` | VARCHAR | wh / dark store |
| `picklist_source_location_label` | VARCHAR | BIN |
| `picklist_item_fsn` | VARCHAR | FSN |
| `irt_ticket_id` | VARCHAR/BIGINT | non-null = INF |
| `irt_ticket_type` | VARCHAR | infraction enum |
| `picklist_assigned_to` | VARCHAR | picker |
| `order_id` | VARCHAR/BIGINT | impacted order |
| `updated_at` | DATETIME | event time |
| `grn_id` | VARCHAR | **demo-added** for inbound-batch signal |

### 2.2 StarRocks — `recommendation_log` (owned)

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT PK | |
| `warehouse_id` | VARCHAR | |
| `bin` | VARCHAR | |
| `fsn` | VARCHAR | |
| `verdict` | VARCHAR | PHANTOM/GENUINE_STOCKOUT/DUAL/AMBIGUOUS |
| `action` | VARCHAR | stocktake/replenish |
| `status` | VARCHAR | suggested/acknowledged/executed/verified |
| `suggested_at` | DATETIME | |
| `resolved_at` | DATETIME | nullable |
| `evidence_ref` | TEXT | cited SQL/graph evidence |
| `failures_before` | INT | |
| `failures_after` | INT | |

### 2.3 NebulaGraph schema

- **Space**: `stockout`
- **Tags**: `FSN(fsn string)`, `BIN(label string, warehouse_id string)`, `Picker(picker_id string)`, `Order(order_id string)`, `GRN(grn_id string)`
- **Edges**: `FAILED_AT(count int, last_seen timestamp)`, `PICKED_FROM()`, `ASSIGNED_TO()`, `RECEIVED_IN()`, `PUTAWAY_TO()`
- **Indexes**: tag indexes on each VID property to support lookups.

---

## 3. Verdict Algorithm (planned)

Implements the PS validation SQL:

```sql
WITH inf AS (
  SELECT reservation_warehouse_id AS wh,
         picklist_source_location_label AS bin,
         picklist_item_fsn AS fsn,
         COUNT(*) AS failures,
         COUNT(DISTINCT order_id) AS orders
  FROM hl_customer_outbound.pendency_mv
  WHERE updated_at >= NOW() - INTERVAL 1 DAY
    AND irt_ticket_id IS NOT NULL
  GROUP BY 1,2,3
),
bin_sum AS (SELECT wh, bin, COUNT(DISTINCT fsn) AS distinct_fsns FROM inf GROUP BY 1,2),
fsn_sum AS (SELECT wh, fsn, COUNT(DISTINCT bin) AS distinct_bins FROM inf GROUP BY 1,2)
SELECT i.*, b.distinct_fsns, f.distinct_bins,
  CASE
    WHEN b.distinct_fsns >= 3 AND f.distinct_bins >= 2 THEN 'DUAL'
    WHEN b.distinct_fsns >= 3 THEN 'PHANTOM'
    WHEN f.distinct_bins >= 2 THEN 'GENUINE_STOCKOUT'
    ELSE 'AMBIGUOUS'
  END AS verdict
FROM inf i
JOIN bin_sum b USING (wh, bin)
JOIN fsn_sum f USING (wh, fsn)
ORDER BY orders DESC;
```

- **Parameters**: `window` (default 1 day), thresholds (constants, default 3 / 2).
- **Recovery projection (planned)**: estimate fill-rate recovery = f(orders impacted)
  per diagnosis; exact formula TBD with ops.

---

## 4. Graph Signal Queries (planned)

| Signal | nGQL sketch |
|--------|-------------|
| Picker overlap | From a BIN, traverse `ASSIGNED_TO` reverse; if >X% of fails share one picker -> flag |
| Shared GRN | From failing FSNs, traverse `RECEIVED_IN`; if they converge on one GRN -> flag |
| Stocktake feedback | From BIN, check `STOCKTAKE`/variance presence post-suggestion |

(Exact nGQL finalized in M6.)

---

## 5. API Contracts (planned)

### `GET /diagnoses`
- **Query params**: `warehouse_id` (optional), `window` (default `1d`).
- **Response**: list of `{ wh, bin, fsn, failures, orders, distinct_fsns, distinct_bins, verdict, action, signals[], recovery_projection }`.

### `POST /ask`
- **Body**: `{ question: string, warehouse_id?: string }`.
- **Response**: `{ answer: string, citations: [{ type: "sql"|"ngql", query, rows }] }`.
- **Rule**: every factual claim maps to a citation.

### `GET /feedback` / `POST /feedback`
- **GET**: returns `recommendation_log` rows with computed `failures_ceased` boolean.
- **POST**: create/update a recommendation (status transitions).

---

## 6. ETL (planned)

- **Trigger**: every 60s (APScheduler/cron).
- **Watermark**: track max `updated_at` processed.
- **Upserts**: `INSERT VERTEX`/`INSERT EDGE` (idempotent) for FSN/BIN/Picker/Order/GRN and edges.
- **Failure handling**: log + retry next cycle; no partial-state corruption (idempotent).

---

## 7. LLM Agent (planned)

- **Models**: Haiku 4.5 (routing/tagging) -> Sonnet 4.6 (reasoning).
- **Tools**: `run_sql(query)`, `run_ngql(query)` — backend-executed, results returned to the model.
- **Citation enforcement**: post-process to ensure each claim references a tool result; reject/repair uncited claims.
- **Guardrails**: read-only queries only; parameterized/whitelisted query patterns to avoid injection.

---

## 8. Security Notes

- Secrets (`ANTHROPIC_API_KEY`, DB creds) via env/`.env` — never committed.
- All DB access read-only except `recommendation_log`.
- LLM-generated queries validated/whitelisted before execution (no arbitrary writes).
- Inputs validated at API boundary (pydantic models).

---

## 9. Implementation Status

| Module | Status |
|--------|--------|
| Repo layout | **done** (M0) |
| Schemas | **done** (M2) |
| Verdict algorithm | **done** (M5) |
| Graph signals | **done** (M6) |
| API contracts | **done** (M5/M7/M8) |
| ETL | **done** (M4) |
| LLM agent | **done** (M7) |
| Frontend | **done** (M9) |
| Docker infra | **done** (M1) |
| Dummy data generator | **done** (M3) |
| E2E demo wiring | pending (M10) |

---

## 10. Change Log

| Date | Change |
|------|--------|
| 2026-06-29 | Initial LLD authored (v1) |
