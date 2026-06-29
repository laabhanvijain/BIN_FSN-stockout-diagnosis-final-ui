# Phase 2 Important Technical Decisions

This file captures the key data-model decisions in Phase 2.

## Decision 1: Use `pendency_mv` As The Source Table

### Choice

Read INF-like event data from:

```text
hl_customer_outbound.pendency_mv
```

### Why

This matches the project guardrail and problem statement. The project should not
invent a new analytics source for the core verdict.

### Trade-Off

The system depends on the quality and completeness of this source. If important
fields are missing or stale, verdicts and graph signals may be weaker.

## Decision 2: Create A Demo Table Instead Of A New StarRocks MV

### Choice

For local demo, create `pendency_mv` as a base table.

### Why

Production already has the source. The local demo needs somewhere to load fake
data.

This still respects the guardrail:

```text
No new StarRocks materialized views.
```

### Trade-Off

The local table is only a demo mirror. It may not perfectly represent production
behavior.

## Decision 3: Use `DUPLICATE KEY` For `pendency_mv`

### Choice

Use:

```text
DUPLICATE KEY(warehouse, bin, fsn)
```

### Why

The same warehouse + BIN + FSN can fail multiple times.

A unique key would lose repeated failures or reject valid rows.

### Trade-Off

Duplicate data must be aggregated carefully later. This is acceptable because
the diagnosis algorithm explicitly counts and groups rows.

## Decision 4: Add Demo `grn_id` Directly To `pendency_mv`

### Choice

Add:

```text
grn_id
```

directly in the demo table.

### Why

This makes the shared-GRN graph signal easy to demonstrate without adding more
tables or joins.

### Trade-Off

In production, GRN may need to come from another inventory/inbound source. The
design doc already marks this as a clarification.

## Decision 5: Use `recommendation_log` For Closed-Loop Feedback

### Choice

Store recommendations and outcomes in:

```text
recommendation_log
```

### Why

The system needs to show:

```text
recommendation -> action -> result
```

This supports auditability and proof that the system's recommendations helped.

### Trade-Off

This adds one system-owned table. It is allowed because it is not a new
StarRocks materialized view and does not replace the source table.

## Decision 6: Use Compound BIN Vertex IDs

### Choice

Represent BIN graph IDs as:

```text
warehouse_id:bin_label
```

Example:

```text
WH-BLR-001:BIN-A
```

### Why

The same BIN label might exist in multiple warehouses.

Using only:

```text
BIN-A
```

could incorrectly merge two different physical locations.

### Trade-Off

Graph IDs become slightly longer, but correctness is better.

## Decision 7: Keep Graph Replica Factor At 1 For Demo

### Choice

Use:

```text
replica_factor = 1
```

### Why

This is a local Docker demo. One replica is simpler and requires fewer storage
containers.

### Trade-Off

This is not production-grade high availability. A production graph cluster would
need stronger replication.

## Decision 8: Seed Deterministic Demo Scenarios

### Choice

Use crafted scenarios instead of purely random data.

### Why

The demo must prove specific behaviors:

```text
phantom
genuine stockout
dual
picker concentration
shared GRN
ambiguous noise
closed-loop feedback
```

### Trade-Off

Crafted demo data may look cleaner than real warehouse data. Real data will have
more noise and edge cases.
