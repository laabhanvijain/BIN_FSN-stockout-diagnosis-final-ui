# Phase 2 Correct Answers

Use this file after answering the Phase 2 checkpoint questions.

## 1. What Table Stores Raw INF-Like Events?

Raw INF-like events are stored in:

```text
hl_customer_outbound.pendency_mv
```

In the local demo, `data/schema/starrocks.sql` creates this as a base table so
dummy data can be loaded.

In production, this source is expected to already exist and should be treated as
read-only.

## 2. What Table Stores Recommendation Feedback?

Recommendation feedback is stored in:

```text
recommendation_log
```

It tracks:

```text
suggestion -> acknowledgement -> execution -> verification
```

It also stores:

```text
failures_before
failures_after
evidence_ref
```

so the system can show whether an action helped.

## 3. What Is A Graph Vertex In This Project?

A graph vertex is a node/entity in NebulaGraph.

Project vertex types include:

```text
FSN
BIN
Picker
Order
GRN
Variance
```

Examples:

```text
FSN-S2-001
WH-BLR-001:BIN-A
PKR-BAD
GRN-SHARED-999
```

## 4. What Is A Graph Edge In This Project?

A graph edge is a relationship between two vertices.

Project edge types include:

```text
FAILED_AT
PICKED_FROM
ASSIGNED_TO
RECEIVED_IN
PUTAWAY_TO
STOCKTAKE
```

Example:

```text
FSN-S2-001 -> FAILED_AT -> WH-BLR-001:BIN-A
```

This means that FSN had an INF/failure at that BIN.

## 5. Why Is A Graph Useful For Picker Or GRN Analysis?

A graph is useful because picker and GRN questions are relationship questions.

Examples:

```text
Are many failures connected to the same picker?
Do failed FSNs share the same inbound GRN batch?
Which BINs are connected to the same GRN?
```

These are easier to express as paths:

```text
Picker -> ASSIGNED_TO -> BIN
FSN -> RECEIVED_IN -> GRN -> PUTAWAY_TO -> BIN
```

StarRocks is strong for counts. NebulaGraph is strong for relationships.
