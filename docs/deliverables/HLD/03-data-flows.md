# HLD 03 · Data Flows

> Status: **M2 schema done** (2026-06-25). Full runtime flows added below.

---

## Data stores (as of M2)

| Store | Role | Key objects |
|-------|------|-------------|
| StarRocks (`hl_customer_outbound`) | SQL analytics — read-only source + owned log | `pendency_mv`, `recommendation_log` |
| NebulaGraph (`stockout`) | Graph store — enrichment signals | Tags: FSN, BIN, Picker, Order, GRN, Variance; Edges: FAILED_AT, PICKED_FROM, ASSIGNED_TO, RECEIVED_IN, PUTAWAY_TO, STOCKTAKE |

---

## Flow 1: Diagnose

```
UI → GET /diagnoses
       └─ verdict SQL (StarRocks) → PHANTOM / GENUINE_STOCKOUT / DUAL / AMBIGUOUS
       └─ enrichment (NebulaGraph) → picker_concentration, shared_grn, stocktake_done
       └─ merge + rank → JSON response (verdict + evidence + recovery projection)
```

## Flow 2: Ask (LLM assistant)

```
UI → POST /ask {question}
       └─ Haiku: route / tag question
       └─ Sonnet: reason with tools
           ├─ run_sql(whitelisted query) → StarRocks
           └─ run_ngql(whitelisted query) → NebulaGraph
       └─ return answer + mandatory citation block
```

## Flow 3: Feedback (closed loop)

```
GET /diagnoses → suggestion row written to recommendation_log (failures_before captured)
Ops: PATCH /feedback/{id}/status → acknowledged → executed
Backend: failures_after computed on status=executed
Closed loop: failures_ceased = failures_before - failures_after ≥ 1 → verified
```

## Flow 4: ETL (StarRocks → NebulaGraph)

```
APScheduler (60s) → read pendency_mv WHERE updated_at > watermark
  → upsert Vertices (FSN, BIN, Picker, Order, GRN)
  → upsert Edges (FAILED_AT, PICKED_FROM, ASSIGNED_TO, RECEIVED_IN, PUTAWAY_TO)
  → update watermark
```
