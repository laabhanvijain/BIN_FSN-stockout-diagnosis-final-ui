# Phase 5 Important Technical Decisions

This file captures the important ETL design decisions.

## Decision 1: Use StarRocks As Source And NebulaGraph As Target

### Choice

Read from:

```text
StarRocks pendency_mv
```

Write to:

```text
NebulaGraph stockout
```

### Why

StarRocks is the source for warehouse failure rows.

NebulaGraph is the relationship layer for picker, GRN, order, and failure paths.

## Decision 2: Incremental Sync With Watermark

### Choice

Use:

```python
_watermark
```

based on `updated_at`.

### Why

The ETL should not reread all rows every minute if only new rows were added.

### Trade-Off

The watermark is in memory. Restarting the backend resets it to year 2000.

For demo, this is fine.

For production, persist it in:

```text
database table
KV store
checkpoint file
workflow/scheduler state
```

## Decision 3: First Run Syncs All Rows

### Choice

Initialize watermark to:

```python
datetime.datetime(2000, 1, 1)
```

### Why

The first sync after startup should copy existing seed/demo rows into
NebulaGraph.

### Trade-Off

After restart, the system may reprocess old rows. This is acceptable only if
graph writes are idempotent.

## Decision 4: Use `IF NOT EXISTS` For Graph Writes

### Choice

Use:

```text
INSERT VERTEX IF NOT EXISTS
INSERT EDGE IF NOT EXISTS
```

### Why

This makes repeated syncs safe from duplicate vertex/edge creation.

### Trade-Off

The name "upsert" in some comments is slightly misleading. `IF NOT EXISTS`
creates missing elements but does not update existing properties.

Example:

```text
FAILED_AT.last_seen may not update if the edge already exists.
```

For demo this is acceptable. For production, decide explicitly whether repeated
events should update graph edge properties or create ranked multi-edges.

## Decision 5: Use Compound BIN VID

### Choice

Use:

```text
warehouse_id:bin_label
```

for BIN vertex IDs.

### Why

The same BIN label can exist in different warehouses.

This prevents cross-warehouse graph collisions.

## Decision 6: Run ETL Inside FastAPI Process

### Choice

Start APScheduler in `backend/main.py`.

### Why

It keeps the demo simple:

```text
one backend process
one scheduler
no separate worker service
```

### Trade-Off

In production, this can be risky if there are multiple backend replicas because
each replica may run the same scheduled job.

Production improvement:

```text
run ETL as a separate worker/scheduler service
```

## Decision 7: Graph Unavailable Means Skip, Not Crash

### Choice

If NebulaGraph session is unavailable:

```text
log warning and skip graph write
```

### Why

The SQL diagnosis layer should still work even if graph enrichment is down.

### Trade-Off

Graph data may become stale until sync succeeds later.

## Decision 8: Swallow ETL Exceptions And Retry Later

### Choice

`run_etl_sync()` catches unexpected exceptions and logs them.

### Why

One failed ETL cycle should not kill the FastAPI process or the scheduler.

### Trade-Off

Silent repeated failures can hide operational issues if logs are not monitored.

Production improvement:

```text
metrics
alerts
retry counters
dead-letter/error table
```
