# Phase 2 Code And Schema Walkthrough

Phase 2 files:

1. `data/schema/starrocks.sql`
2. `data/schema/nebula.ngql`
3. `data/generate_dummy_data.py`
4. `docs/deliverables/LLD/02-data-schemas.md`

This phase explains what data exists, why it exists, and how the demo scenarios
are created.

## File 1: `data/schema/starrocks.sql`

### Purpose

This file creates the StarRocks database and tables for the local demo.

In production, the source table is expected to already exist. For the demo, this
file creates a table shaped like the real WMS source so dummy data can be loaded.

### Database

```sql
CREATE DATABASE IF NOT EXISTS hl_customer_outbound;
USE hl_customer_outbound;
```

Beginner translation:

```text
Create a database named hl_customer_outbound if it does not already exist.
Then make that database the active one.
```

### Table 1: `pendency_mv`

This is the most important StarRocks table for diagnosis.

It stores WMS-like INF event data.

Important columns:

| Column | Meaning |
|---|---|
| `reservation_warehouse_id` | Which warehouse/dark store. |
| `picklist_source_location_label` | Which BIN/location. |
| `picklist_item_fsn` | Which product/item. |
| `irt_ticket_id` | Non-null means active INF-like event. |
| `irt_ticket_type` | Type of infraction, such as INF. |
| `picklist_assigned_to` | Picker ID. |
| `order_id` | Customer order affected. |
| `grn_id` | Demo inbound batch ID for shared-GRN graph signal. |
| `updated_at` | Event timestamp. |

The key Phase 2 idea:

```text
pendency_mv is the raw source for diagnosis.
```

### Why `irt_ticket_id` Matters

The verdict algorithm filters:

```text
irt_ticket_id IS NOT NULL
```

Meaning:

```text
Only rows with an inventory-resolution ticket are treated as active failures.
```

### Why `grn_id` Is Special

The schema comments say `grn_id` is demo-only.

Reason:

```text
Real production data may need to join GRN from inventory/inbound tables.
For this demo, grn_id is placed directly on pendency_mv to keep setup simple.
```

This supports the graph signal:

```text
Did multiple failed FSNs come from the same inbound batch?
```

### Duplicate Key

```sql
DUPLICATE KEY(reservation_warehouse_id, picklist_source_location_label, picklist_item_fsn)
```

Beginner translation:

```text
Allow multiple rows for the same warehouse + BIN + FSN.
```

Why?

Because the same FSN can fail multiple times at the same BIN. We do not want a
unique key that overwrites or rejects older failures.

### Table 2: `recommendation_log`

This table is owned by this system.

It tracks:

```text
suggestion -> action -> outcome
```

Important columns:

| Column | Meaning |
|---|---|
| `id` | Row identifier. |
| `warehouse_id` | Target warehouse. |
| `bin` | Target BIN. |
| `fsn` | Target FSN. |
| `verdict` | Diagnosis verdict. |
| `action` | Suggested action. |
| `status` | Lifecycle status. |
| `suggested_at` | When recommendation was made. |
| `resolved_at` | When recommendation was verified. |
| `evidence_ref` | Evidence string for auditability. |
| `failures_before` | Failures before action. |
| `failures_after` | Failures after action. |

This table enables the feedback loop.

## File 2: `data/schema/nebula.ngql`

### Purpose

This file creates the NebulaGraph schema.

NebulaGraph is used for relationship queries.

### Space

```ngql
CREATE SPACE IF NOT EXISTS stockout (
    partition_num  = 10,
    replica_factor = 1,
    vid_type       = FIXED_STRING(128)
);
```

Beginner translation:

```text
Create a graph database named stockout.
Use string IDs for graph nodes.
Use one replica because this is a local demo.
```

### Tags

In NebulaGraph, a tag is a node type.

The project defines:

```text
FSN
BIN
Picker
Order
GRN
Variance
```

Meaning:

```text
FSN = product node
BIN = physical location node
Picker = picker node
Order = order node
GRN = inbound batch node
Variance = stocktake/variance node
```

### Edges

An edge is a relationship between nodes.

The project defines:

| Edge | Direction | Meaning |
|---|---|---|
| `FAILED_AT` | FSN -> BIN | This FSN had an INF at this BIN. |
| `PICKED_FROM` | Order -> BIN | This order was picked from this BIN. |
| `ASSIGNED_TO` | Picker -> BIN | This picker was assigned at this BIN. |
| `RECEIVED_IN` | FSN -> GRN | This FSN came from this inbound batch. |
| `PUTAWAY_TO` | GRN -> BIN | This GRN was put away to this BIN. |
| `STOCKTAKE` | BIN -> Variance | A stocktake/variance signal exists for this BIN. |

### Indexes

The schema creates indexes on important lookup properties:

```text
fsn
bin label
warehouse_id
picker_id
order_id
grn_id
```

Why?

Because graph queries often need to find a node by property before traversing
relationships.

## File 3: `data/generate_dummy_data.py`

### Purpose

This file seeds StarRocks with known demo data.

The data is intentionally shaped to trigger known verdicts and graph signals.

### Global Constants

```python
SEED = 42
WH = "WH-BLR-001"
BASE_DT = datetime.datetime.now() - datetime.timedelta(hours=6)
```

Meaning:

```text
Use a fixed random seed for reproducibility.
Use one demo warehouse.
Set event timestamps within the default diagnosis window.
```

### Helper Functions

`_dt(offset_minutes)` creates a timestamp.

`_irt()` creates a fake IRT ticket ID.

`_order()` creates a fake order ID.

`make_row(...)` builds one `pendency_mv` row as a Python dictionary.

That dictionary has the same fields as the StarRocks table:

```text
warehouse
bin
fsn
irt ticket
ticket type
picker
order
grn
updated_at
```

### Scenario S1: Phantom

```python
scenario_s1_phantom()
```

Shape:

```text
5 distinct FSNs fail in BIN-PHANTOM-A
```

Expected SQL verdict:

```text
PHANTOM_INVENTORY
```

### Scenario S2: Genuine Stockout

```python
scenario_s2_genuine()
```

Shape:

```text
FSN-S2-001 fails in 3 different BINs
```

Expected SQL verdict:

```text
GENUINE_STOCKOUT
```

### Scenario S3: Dual

```python
scenario_s3_dual()
```

Shape:

```text
BIN-DUAL-A has many FSNs failing.
One of those FSNs also fails in other BINs.
```

Expected verdict:

```text
DUAL
```

### Scenario S4: Picker Driven

```python
scenario_s4_picker()
```

Shape:

```text
4 distinct FSNs fail in BIN-PICKER-A.
All are assigned to picker PKR-BAD.
```

SQL verdict:

```text
PHANTOM_INVENTORY
```

Graph enrichment:

```text
picker concentration
```

This is a great example of why the graph matters:

```text
SQL says BIN pattern.
Graph suggests picker/process context.
```

### Scenario S5: Shared GRN

```python
scenario_s5_shared_grn()
```

Shape:

```text
4 distinct FSNs fail in BIN-GRN-A.
All share GRN-SHARED-999.
```

SQL verdict:

```text
PHANTOM_INVENTORY
```

Graph enrichment:

```text
shared inbound batch
```

### Scenario S6: Noise / Ambiguous

```python
scenario_s6_noise()
```

Shape:

```text
isolated single failures
no threshold crossed
```

Expected verdict:

```text
AMBIGUOUS
```

### Recommendation Rows

`recommendation_log_rows()` creates two already-verified recommendation rows.

These support the feedback UI demo.

Example lifecycle:

```text
status = verified
failures_before = 10
failures_after = 0
```

Meaning:

```text
The action appears to have reduced failures.
```

### Insert Helpers

`connect(...)` connects to StarRocks.

`insert_pendency_rows(...)` inserts failure rows.

`insert_rec_log_rows(...)` inserts recommendation rows.

`clear_tables(...)` truncates both demo tables.

`main()` wires everything together:

```text
parse command-line args
connect to StarRocks
optionally clear tables
build all scenario rows
insert pendency_mv rows
insert recommendation_log rows
print expected verdict map
```

## File 4: `docs/deliverables/LLD/02-data-schemas.md`

### Purpose

This file documents the same schemas in explanation form.

It is useful because it explains why schema choices were made.

Important design notes:

```text
pendency_mv is a demo table mirror of the real source.
No new StarRocks materialized view is created.
Duplicate key allows repeated failures.
BIN graph IDs use warehouse + label to avoid cross-warehouse collisions.
replication_num=1 and replica_factor=1 are for local demo simplicity.
```

## Phase 2 Runtime Example

Take this demo row:

```text
warehouse = WH-BLR-001
bin = BIN-PICKER-A
fsn = FSN-S4-001
picker = PKR-BAD
grn = GRN-BATCH-004
order = ORD-123456
```

In StarRocks, it is one row in:

```text
pendency_mv
```

Later, ETL can convert it into graph relationships:

```text
FSN-S4-001 -> FAILED_AT -> WH-BLR-001:BIN-PICKER-A
PKR-BAD -> ASSIGNED_TO -> WH-BLR-001:BIN-PICKER-A
ORD-123456 -> PICKED_FROM -> WH-BLR-001:BIN-PICKER-A
FSN-S4-001 -> RECEIVED_IN -> GRN-BATCH-004
GRN-BATCH-004 -> PUTAWAY_TO -> WH-BLR-001:BIN-PICKER-A
```

That is the bridge from table data to graph data.

## Phase 2 Takeaways

1. `pendency_mv` is the main source table for INF-like events.
2. `recommendation_log` stores the closed-loop feedback lifecycle.
3. StarRocks stores table data for SQL aggregation.
4. NebulaGraph stores nodes and edges for relationship queries.
5. Dummy data is carefully designed to prove each verdict and graph signal.

## One-Time Seed Vs Continuous Generation

There are two different data-generation scripts in the project.

### 1. `data/generate_dummy_data.py`

This is the one-time deterministic seed script.

It contains:

```python
BASE_DT = datetime.datetime.now() - datetime.timedelta(hours=6)
```

Meaning:

```text
Start seeded event timestamps around 6 hours before the current time.
```

Then each scenario adds minute offsets using:

```python
_dt(offset_minutes)
```

Because the default diagnosis window is:

```text
last 1 day
```

the seeded rows are intentionally inside the active diagnosis window.

Important:

```text
generate_dummy_data.py does not continuously generate rows.
It inserts a fixed demo dataset once per run.
```

Typical command:

```bash
python data/generate_dummy_data.py --clear
```

### 2. `data/data_generator.py`

This is the continuous/live data generator.

It has:

```python
parser.add_argument("--interval", type=int, default=2)
```

Meaning:

```text
By default, generate one batch every 2 seconds.
```

Run continuously:

```bash
python data/data_generator.py
```

Generate once:

```bash
python data/data_generator.py --once
```

Use a custom interval:

```bash
python data/data_generator.py --interval 5
```

Meaning:

```text
Generate one batch every 5 seconds.
```

Generate a limited number of batches:

```bash
python data/data_generator.py --batches 10
```

The event rotation is:

```text
repeat -> repeat -> inventory_adjust -> new_bin -> new_fsn
```

Important caution:

```text
data/data_generator.py references an inventory_items table in some event types,
but Phase 2's StarRocks schema only creates pendency_mv and recommendation_log.
```

So the continuous generator may need extra schema support or adjustment before
all event types run cleanly.

Simple memory hook:

```text
generate_dummy_data.py = one-time known demo stories
data_generator.py      = repeated/live event stream
```
