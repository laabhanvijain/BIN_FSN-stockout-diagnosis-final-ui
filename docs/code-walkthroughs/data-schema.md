# data/schema/ — Code Walkthrough

> Source: `data/schema/starrocks.sql`, `data/schema/nebula.ngql`
> Milestone: M2 · Last updated: 2026-06-25

## What it does

Defines every table and graph object the system reads from or writes to.
Two files — one per store type.

---

## starrocks.sql

### `pendency_mv` (read-only source)

Mirrors the real WMS `hl_customer_outbound.pendency_mv` table exactly, plus
one demo-only column `grn_id`.

| Column | Type | Why it exists |
|--------|------|---------------|
| `reservation_warehouse_id` | VARCHAR | Identifies the dark store (wh) |
| `picklist_source_location_label` | VARCHAR | Physical BIN label |
| `picklist_item_fsn` | VARCHAR | Product identifier |
| `irt_ticket_id` | VARCHAR | Non-null = active INF event (the filter) |
| `irt_ticket_type` | VARCHAR | Infraction enum (e.g. INF) |
| `picklist_assigned_to` | VARCHAR | Picker ID — used for picker-concentration signal |
| `order_id` | VARCHAR | Impacted customer order |
| `grn_id` | VARCHAR | **Demo-only**: inbound GRN for the shared-batch signal |
| `updated_at` | DATETIME | Event timestamp; ETL watermark key |

**Distribution**: `HASH(reservation_warehouse_id)` — all rows for one dark store
land in the same bucket, making per-warehouse queries fast.

**`DUPLICATE KEY`**: StarRocks DUPLICATE key model is used (not AGGREGATE/UNIQUE)
because the same (wh, bin, fsn) tuple can appear many times with different
timestamps — one row per INF event.

### `recommendation_log` (owned by this system)

Tracks the closed feedback loop. One row per suggestion, advancing through
`suggested → acknowledged → executed → verified`.

`failures_before` is set when the row is created; `failures_after` is filled
when an action is executed/verified, allowing us to compute `failures_ceased`.

---

## nebula.ngql

### Space: `stockout`

One logical NebulaGraph database. `partition_num=10` distributes data across
partitions for parallelism; `replica_factor=1` is fine for a local demo.

### Tags (nodes)

| Tag | VID format | Key properties |
|-----|-----------|----------------|
| FSN | `<fsn>` | fsn |
| BIN | `<wh>:<label>` | label, warehouse_id |
| Picker | `<picker_id>` | picker_id |
| Order | `<order_id>` | order_id |
| GRN | `<grn_id>` | grn_id |
| Variance | `<variance_id>` | variance_id, variance_type |

**BIN VID design**: combining `wh + label` in the VID (e.g. `WH-001:F1-05-5D`)
ensures BINs with the same label in different warehouses are distinct nodes.

### Edges

| Edge | From → To | Carries | Signal it enables |
|------|-----------|---------|-------------------|
| FAILED_AT | FSN → BIN | last_seen timestamp | Core PHANTOM/GENUINE verdict |
| PICKED_FROM | Order → BIN | — | Order-level tracing |
| ASSIGNED_TO | Picker → BIN | — | Picker concentration signal |
| RECEIVED_IN | FSN → GRN | — | Shared inbound batch signal |
| PUTAWAY_TO | GRN → BIN | — | Shared inbound batch signal |
| STOCKTAKE | BIN → Variance | done_at timestamp | Closed-loop feedback signal |

### Indexes

All tag indexes are on the key lookup property (32-char prefix). `REBUILD TAG INDEX`
is called immediately so indexes are active before data is loaded.

---

## Technical decisions

| Decision | Options | Choice | Why |
|----------|---------|--------|-----|
| BIN VID = `wh:label` | Label only vs compound | Compound | Same BIN label can exist in multiple warehouses |
| DUPLICATE KEY in StarRocks | AGGREGATE / UNIQUE / DUPLICATE | DUPLICATE | Multiple INF events per (wh,bin,fsn) are all valid rows |
| `grn_id` as demo column | New join table vs column on pendency_mv | Column | Avoids a new MV; respects the PS guardrail |
| `replica_factor=1` | 1 vs 3 | 1 | Local demo; 3 replicas need 3 storage nodes |
