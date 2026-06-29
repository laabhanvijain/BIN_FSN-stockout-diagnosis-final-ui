# Phase 5 Code Walkthrough

Phase 5 files:

1. `backend/etl/sync.py`
2. `backend/main.py`
3. `data/schema/nebula.ngql`
4. `docs/code-walkthroughs/etl-sync.md`

This phase explains how StarRocks rows become NebulaGraph vertices and edges.

## File 1: `backend/etl/sync.py`

### Purpose

This file defines the ETL job:

```text
StarRocks pendency_mv -> NebulaGraph stockout space
```

It reads new INF rows from StarRocks and writes graph vertices and edges into
NebulaGraph.

The job is scheduled from `backend/main.py`.

## Watermark

```python
_watermark: datetime.datetime = datetime.datetime(2000, 1, 1)
```

This stores the latest `updated_at` timestamp already synced.

Because it starts at year 2000:

```text
first run syncs all current rows
```

Important limitation:

```text
The watermark is in memory.
If the backend restarts, it resets to year 2000.
```

For the demo, this is acceptable because graph inserts are intended to be safe
on repeated runs. In production, the watermark should be persisted.

## `_FETCH_SQL`

```sql
SELECT
    reservation_warehouse_id AS wh,
    picklist_source_location_label AS bin,
    picklist_item_fsn AS fsn,
    picklist_assigned_to AS picker,
    order_id,
    grn_id,
    updated_at
FROM pendency_mv
WHERE irt_ticket_id IS NOT NULL
  AND updated_at > %(watermark)s
ORDER BY updated_at
```

Beginner translation:

```text
Read StarRocks rows from pendency_mv.
Keep only INF-like rows with irt_ticket_id.
Only fetch rows newer than the watermark.
Order oldest to newest.
```

The selected fields are exactly what the graph needs:

```text
warehouse, bin, fsn, picker, order, grn, timestamp
```

## `_esc(value)`

```python
def _esc(value: str) -> str:
    return str(value).replace("'", "\\'")
```

This escapes single quotes before embedding values inside nGQL strings.

It is a small safety helper for generated graph queries.

## `_bin_vid(wh, label)`

```python
def _bin_vid(wh: str, label: str) -> str:
    return f"{_esc(wh)}:{_esc(label)}"
```

This creates the graph ID for a BIN.

Example:

```text
WH-BLR-001:BIN-PICKER-A
```

Why include warehouse?

Because different warehouses may have the same BIN label.

## `_upsert_vertices(session, rows)`

This function creates graph nodes.

For each StarRocks row, it may create:

```text
FSN
BIN
Picker
Order
GRN
```

It builds value lists:

```python
fsn_vals
bin_vals
picker_vals
order_vals
grn_vals
```

Then it creates nGQL statements like:

```ngql
INSERT VERTEX IF NOT EXISTS FSN(fsn) VALUES "FSN-S1-001":("FSN-S1-001");
```

and:

```ngql
INSERT VERTEX IF NOT EXISTS BIN(label,warehouse_id)
VALUES "WH-BLR-001:BIN-A":("BIN-A","WH-BLR-001");
```

Important:

```text
IF NOT EXISTS means do not create a duplicate if the vertex already exists.
```

## `_upsert_edges(session, rows)`

This function creates graph relationships.

For each StarRocks row, it may create:

```text
FAILED_AT
PICKED_FROM
ASSIGNED_TO
RECEIVED_IN
PUTAWAY_TO
```

Examples:

```ngql
INSERT EDGE IF NOT EXISTS FAILED_AT(last_seen)
VALUES "FSN-S1-001"->"WH-BLR-001:BIN-A"@0:(timestamp);
```

Meaning:

```text
This FSN failed at this BIN.
```

```ngql
INSERT EDGE IF NOT EXISTS ASSIGNED_TO()
VALUES "PKR-001"->"WH-BLR-001:BIN-A"@0:();
```

Meaning:

```text
This picker was assigned to this BIN.
```

The edge rank is:

```text
@0
```

Meaning:

```text
Use one edge between the same source and destination for this relationship type.
```

## `run_etl_sync()`

This is the main ETL function.

Flow:

```text
open StarRocks connection
fetch rows newer than watermark
close StarRocks connection
if no rows, return
open NebulaGraph session
write vertices
write edges
advance watermark to latest updated_at
log success
```

If NebulaGraph is unavailable:

```python
if session is None:
    logger.warning(...)
    return
```

So graph sync fails gracefully.

If anything unexpected fails:

```python
except Exception:
    logger.exception(...)
```

The exception is swallowed so the scheduler can retry next interval.

## Important Nuance: Upsert Wording

Some comments/docs describe the graph writes as "upserts" or overwrites.

The actual nGQL uses:

```text
INSERT ... IF NOT EXISTS
```

That means:

```text
create if missing
skip if already exists
```

It is safe for repeated runs, but it may not update properties like
`FAILED_AT.last_seen` if the edge already exists.

For this demo, that is acceptable. In production, we would be more explicit
about whether graph properties should update on repeated events.

## File 2: `backend/main.py`

### Purpose In Phase 5

`main.py` starts the scheduler.

Startup code:

```python
scheduler = BackgroundScheduler()
scheduler.add_job(run_etl_sync, "interval", minutes=1, id="etl_sync")
scheduler.start()
```

Meaning:

```text
Run run_etl_sync every 1 minute in the background.
```

Shutdown:

```python
scheduler.shutdown(wait=False)
```

Meaning:

```text
Stop the scheduler when the backend stops.
```

## File 3: `data/schema/nebula.ngql`

This file defines the graph structure that ETL writes into.

Tags:

```text
FSN
BIN
Picker
Order
GRN
Variance
```

Edges:

```text
FAILED_AT
PICKED_FROM
ASSIGNED_TO
RECEIVED_IN
PUTAWAY_TO
STOCKTAKE
```

Phase 5 writes all except:

```text
Variance
STOCKTAKE
```

Those are for later closed-loop stocktake signals.

## File 4: `docs/code-walkthroughs/etl-sync.md`

This older walkthrough correctly explains the main flow:

```text
every 60 seconds
read rows newer than watermark
write vertices and edges
advance watermark
```

But remember the nuance:

```text
actual code uses IF NOT EXISTS, so existing graph elements are skipped, not updated.
```

## End-To-End Phase 5 Flow

```text
FastAPI starts
  -> lifespan runs
  -> init_nebula_pool()
  -> APScheduler starts
  -> every 1 minute run_etl_sync()
  -> run_etl_sync reads new StarRocks rows
  -> creates FSN/BIN/Picker/Order/GRN vertices
  -> creates FAILED_AT/PICKED_FROM/ASSIGNED_TO/RECEIVED_IN/PUTAWAY_TO edges
  -> advances watermark
```

## Concrete Example

Input StarRocks row:

```text
wh = WH-BLR-001
bin = BIN-PICKER-A
fsn = FSN-S4-001
picker = PKR-BAD
order_id = ORD-123456
grn_id = GRN-BATCH-004
```

Vertices created:

```text
FSN-S4-001
WH-BLR-001:BIN-PICKER-A
PKR-BAD
ORD-123456
GRN-BATCH-004
```

Edges created:

```text
FSN-S4-001 -> FAILED_AT -> WH-BLR-001:BIN-PICKER-A
ORD-123456 -> PICKED_FROM -> WH-BLR-001:BIN-PICKER-A
PKR-BAD -> ASSIGNED_TO -> WH-BLR-001:BIN-PICKER-A
FSN-S4-001 -> RECEIVED_IN -> GRN-BATCH-004
GRN-BATCH-004 -> PUTAWAY_TO -> WH-BLR-001:BIN-PICKER-A
```

## Phase 5 Takeaways

1. ETL means extract, transform, load.
2. Source is StarRocks `pendency_mv`.
3. Target is NebulaGraph `stockout`.
4. `_watermark` makes sync incremental.
5. First backend run syncs all rows because watermark starts at year 2000.
6. ETL runs every 1 minute from `backend/main.py`.
7. One StarRocks row can become several graph vertices and edges.
