# Phase 5 Prerequisites

Phase 5 is about ETL from StarRocks to NebulaGraph.

Before reading the code, understand these ideas:

1. ETL
2. Source and target
3. Incremental sync
4. Watermark
5. Upsert / idempotency
6. Scheduler
7. Graph vertex and edge creation

## 1. ETL

ETL means:

```text
Extract
Transform
Load
```

In this project:

```text
Extract  = read INF rows from StarRocks
Transform = convert rows into graph nodes and relationships
Load     = write those nodes and relationships into NebulaGraph
```

## 2. Source And Target

The source is where data comes from.

The target is where data goes.

In Phase 5:

```text
source = StarRocks pendency_mv
target = NebulaGraph stockout space
```

## 3. Incremental Sync

Incremental sync means:

```text
Only copy rows that are new since the previous sync.
```

This is better than copying all rows every minute forever.

## 4. Watermark

A watermark remembers how far the sync has progressed.

In this project, the watermark is:

```text
latest updated_at timestamp already synced
```

Example:

```text
watermark = 2026-06-30 10:00:00
```

Next sync asks:

```text
Give me rows where updated_at > 2026-06-30 10:00:00
```

## 5. Upsert And Idempotency

Idempotency means:

```text
Running the same operation more than once should not create incorrect duplicates.
```

In graph sync, this matters because the first backend start may sync many rows,
and a retry may process rows again.

The code uses:

```text
INSERT VERTEX IF NOT EXISTS
INSERT EDGE IF NOT EXISTS
```

Meaning:

```text
Create the graph element if it is missing.
If it already exists, skip it.
```

## 6. Scheduler

A scheduler runs a function on a time interval.

In this project:

```text
APScheduler runs run_etl_sync every 1 minute.
```

This is started in `backend/main.py`.

## 7. Graph Vertex And Edge Creation

One StarRocks row can create multiple graph entities.

Example row:

```text
warehouse = WH-BLR-001
bin = BIN-A
fsn = FSN-1
picker = PKR-001
order = ORD-123
grn = GRN-999
```

Possible graph vertices:

```text
FSN-1
WH-BLR-001:BIN-A
PKR-001
ORD-123
GRN-999
```

Possible graph edges:

```text
FSN-1 -> FAILED_AT -> WH-BLR-001:BIN-A
ORD-123 -> PICKED_FROM -> WH-BLR-001:BIN-A
PKR-001 -> ASSIGNED_TO -> WH-BLR-001:BIN-A
FSN-1 -> RECEIVED_IN -> GRN-999
GRN-999 -> PUTAWAY_TO -> WH-BLR-001:BIN-A
```

## Phase 5 Mental Model

```text
Every minute:
  read new INF rows from StarRocks
  turn each row into graph vertices and edges
  write them into NebulaGraph
  advance watermark
```

Simple memory hook:

```text
StarRocks rows -> ETL sync -> NebulaGraph relationships
```
