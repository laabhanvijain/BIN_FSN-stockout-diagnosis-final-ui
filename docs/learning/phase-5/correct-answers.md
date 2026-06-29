# Phase 5 Correct Answers

Use this after answering Phase 5 checkpoint questions.

## 1. Where Does The ETL Read From?

The ETL reads from:

```text
StarRocks table hl_customer_outbound.pendency_mv
```

Specifically, it reads rows where:

```text
irt_ticket_id IS NOT NULL
updated_at > watermark
```

## 2. Where Does The ETL Write To?

The ETL writes to:

```text
NebulaGraph space stockout
```

It writes graph vertices and edges.

## 3. Why Is The ETL Scheduled Every Minute?

It runs every minute so NebulaGraph stays reasonably fresh as new INF rows arrive
in StarRocks.

This lets graph signals and assistant investigations use recent relationship
data.

## 4. What Vertices Are Created?

For each row, the ETL may create:

```text
FSN
BIN
Picker
Order
GRN
```

The `Variance` vertex exists in the schema but is not created by the main
pendency row ETL path.

## 5. What Edges Are Created?

For each row, the ETL may create:

```text
FAILED_AT
PICKED_FROM
ASSIGNED_TO
RECEIVED_IN
PUTAWAY_TO
```

Meaning:

```text
FSN -> FAILED_AT -> BIN
Order -> PICKED_FROM -> BIN
Picker -> ASSIGNED_TO -> BIN
FSN -> RECEIVED_IN -> GRN
GRN -> PUTAWAY_TO -> BIN
```

The `STOCKTAKE` edge exists in the schema but is not created by this main row
sync.
