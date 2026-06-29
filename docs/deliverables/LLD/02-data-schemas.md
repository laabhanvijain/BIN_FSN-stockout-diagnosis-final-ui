# LLD 02 · Data Schemas

> Status: **DONE** (M2 schema · M3 dummy data · 2026-06-25). Source files: `data/schema/starrocks.sql`, `data/schema/nebula.ngql`, `data/generate_dummy_data.py`.

---

## StarRocks — `hl_customer_outbound.pendency_mv` (read-only source)

Mirror of the real WMS table. We create it with `CREATE TABLE` (not a view/MV) for
the demo. The PS guardrail is "no new StarRocks MVs"; this DDL creates only a base table.

| Column | Type | Notes |
|--------|------|-------|
| `reservation_warehouse_id` | VARCHAR(64) | Dark store / warehouse ID |
| `picklist_source_location_label` | VARCHAR(64) | Physical BIN label (e.g. F1-05-5D) |
| `picklist_item_fsn` | VARCHAR(64) | Flipkart Serial Number (product) |
| `irt_ticket_id` | VARCHAR(64) | Non-null = active INF event (the filter) |
| `irt_ticket_type` | VARCHAR(32) | Infraction enum (e.g. INF) |
| `picklist_assigned_to` | VARCHAR(64) | Picker employee ID — used for picker-concentration signal |
| `order_id` | VARCHAR(64) | Impacted customer order |
| `grn_id` | VARCHAR(64) | **Demo-only**: inbound GRN for the shared-batch graph signal |
| `updated_at` | DATETIME | Event timestamp; ETL watermark key |

**Key design choices:**
- `DUPLICATE KEY(wh, bin, fsn)` — allows multiple INF events per triple (correct; UNIQUE would drop older events).
- `DISTRIBUTED BY HASH(reservation_warehouse_id)` — per-warehouse queries touch fewer buckets.
- `replication_num=1` — single-node local demo.

---

## StarRocks — `recommendation_log` (owned by this system)

Tracks each suggestion through its full lifecycle. Enables the closed feedback loop.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT AUTO_INCREMENT | Primary key |
| `warehouse_id` | VARCHAR(64) | Target warehouse |
| `bin` | VARCHAR(64) | Target BIN |
| `fsn` | VARCHAR(64) | Target FSN |
| `verdict` | VARCHAR(32) | `PHANTOM \| GENUINE_STOCKOUT \| DUAL \| AMBIGUOUS` |
| `action` | VARCHAR(64) | `stocktake \| replenish \| stocktake + replenish \| investigate` |
| `status` | VARCHAR(32) | `suggested → acknowledged → executed → verified` |
| `suggested_at` | DATETIME | When the system made the recommendation |
| `resolved_at` | DATETIME | Set when status reaches `verified` |
| `evidence_ref` | TEXT | Cited SQL/graph evidence string for auditability |
| `failures_before` | INT | INF count at suggestion time (for delta) |
| `failures_after` | INT | INF count after action executed (for closed-loop verification) |

---

## NebulaGraph — space `stockout`

**Space config**: `partition_num=10`, `replica_factor=1`, `vid_type=FIXED_STRING(128)`.

### Tags (node types)

| Tag | VID convention | Key properties | Signal enabled |
|-----|---------------|----------------|----------------|
| `FSN` | `<fsn>` | `fsn` | Core |
| `BIN` | `<wh_id>:<label>` | `label`, `warehouse_id` | Core (compound VID = uniqueness across warehouses) |
| `Picker` | `<picker_id>` | `picker_id` | Picker concentration |
| `Order` | `<order_id>` | `order_id` | Order tracing |
| `GRN` | `<grn_id>` | `grn_id` | Shared inbound batch |
| `Variance` | `<variance_id>` | `variance_id`, `variance_type` | Closed-loop stocktake |

### Edge types

| Edge | Direction | Properties | Signal enabled |
|------|-----------|------------|----------------|
| `FAILED_AT` | FSN → BIN | `last_seen INT64` | Core PHANTOM/GENUINE verdict |
| `PICKED_FROM` | Order → BIN | — | Order-level tracing |
| `ASSIGNED_TO` | Picker → BIN | — | Picker concentration |
| `RECEIVED_IN` | FSN → GRN | — | Shared inbound batch |
| `PUTAWAY_TO` | GRN → BIN | — | Shared inbound batch |
| `STOCKTAKE` | BIN → Variance | `done_at INT64` | Closed-loop feedback |

### Indexes

Tag indexes on every key lookup property (32-char prefix). `REBUILD TAG INDEX` is
called immediately in the DDL script so indexes are active before data is loaded.

---

## Key Technical Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| BIN VID compound | `wh_id:label` | Label only | Same BIN label in two warehouses must be distinct nodes |
| StarRocks key model | DUPLICATE | AGGREGATE, UNIQUE | Multiple events per (wh,bin,fsn) all count |
| `grn_id` placement | Column on `pendency_mv` | Separate join table | Respects "no new MV" guardrail; simpler demo loading |
| `Variance` tag | Separate tag | Property on BIN | Enables edge from BIN → Variance (closed-loop STOCKTAKE edge) |
| `replica_factor=1` | 1 | 3 | Single-node Docker demo; 3 replicas need 3 storage containers |
