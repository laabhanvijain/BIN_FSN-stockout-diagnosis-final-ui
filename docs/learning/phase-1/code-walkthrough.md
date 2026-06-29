# Phase 1 Code And Document Walkthrough

Phase 1 files:

1. `design/design-doc.md`
2. `docs/deliverables/HLD/01-context-and-goals.md`
3. `docs/deliverables/LLD/03-verdict-algorithm.md`

This phase is mostly about documents and algorithm design, not implementation
code yet. The implementation file `backend/services/diagnosis.py` comes in
Phase 4, but the algorithm is already specified here.

## File 1: `design/design-doc.md`

### Purpose

This is the main design document. It explains the project problem, core
diagnostic logic, architecture, data model, dummy scenarios, success metrics, and
risks.

For Phase 1, the most important sections are:

1. Problem 1-Pager
2. Core Diagnostic Logic
3. Design Decision DD-1
4. Success Metrics
5. Open Clarifications

### Problem 1-Pager

The file says:

```text
In Flipkart Hyperlocal dark stores, items (FSN) live in labeled slots (BIN).
When a picker cannot find an FSN in its BIN, they raise an INF.
```

This gives the domain setup:

```text
FSN = item/product
BIN = physical storage location
INF = pick failure signal
IRT = ticket created for inventory investigation
```

The business pain is:

```text
Existing S11 signal says which FSN/BIN pairs failed,
but it does not explain the root cause.
```

So the goal is:

```text
Reduce diagnosis from 3-5 days to minutes.
```

### Core Diagnostic Logic

This is the heart of Phase 1.

The system uses two axes:

```text
Axis 1: How many distinct FSNs failed in this BIN?
Axis 2: How many distinct BINs did this FSN fail across?
```

If many distinct FSNs fail in the same BIN:

```text
Root cause: PHANTOM INVENTORY
Action: stocktake the BIN
```

If the same FSN fails across many distinct BINs:

```text
Root cause: GENUINE STOCKOUT
Action: replenish the FSN
```

### Verdict Thresholds

The design doc defines:

```text
distinct_fsns >= 3 AND distinct_bins >= 2 -> DUAL
distinct_fsns >= 3                        -> PHANTOM
distinct_bins >= 2                        -> GENUINE_STOCKOUT
else                                      -> AMBIGUOUS
```

This means each diagnosis row has two important numbers:

```text
distinct_fsns
distinct_bins
```

Then the verdict is assigned using a fixed rule.

### Why DUAL Comes First

The `DUAL` check must happen before the individual checks.

Example:

```text
distinct_fsns = 4
distinct_bins = 3
```

This satisfies both:

```text
distinct_fsns >= 3
distinct_bins >= 2
```

If we checked phantom first, we would incorrectly stop at `PHANTOM_INVENTORY`.
By checking `DUAL` first, the system preserves the fact that both patterns are
active.

### Design Decision DD-1

DD-1 says the project keeps the problem statement's verdict logic as the
deterministic core.

The important design point:

```text
Do not use ML to invent new thresholds.
Use fixed, explainable rules.
```

Why:

- The spec already defines/validates the SQL logic.
- The success metric is analyst agreement.
- Deterministic rules are easier to audit.
- ML forecasting is explicitly out of scope.

### What To Skim In Phase 1

For Phase 1, you can skim:

- Detailed Docker/runtime sections
- LLM tool-calling details
- Full graph signal table
- UI surfaces

Those become important in later phases.

## File 2: `docs/deliverables/HLD/01-context-and-goals.md`

### Purpose

This is the high-level design summary for context and goals.

It is short but important because it defines:

- purpose
- in scope
- out of scope
- success metrics

### Purpose Section

The key statement:

```text
Reduce BIN-FSN stockout diagnosis from 3-5 days to minutes.
```

The method:

```text
Auto-classify INF events into PHANTOM vs GENUINE STOCKOUT
with cited, actionable recommendations.
```

This confirms the project is not only a dashboard. It is a diagnosis and
recommendation system.

### In Scope

The HLD says the project includes:

```text
Read-only over hl_customer_outbound.pendency_mv
Local Dockerized StarRocks + NebulaGraph
React UI
FastAPI backend
LLM agent
Closed-loop capture in recommendation_log
```

For Phase 1, the key part is:

```text
Read-only over hl_customer_outbound.pendency_mv
```

That means the project reads warehouse failure data but does not create new
StarRocks materialized views.

### Out Of Scope

The HLD explicitly excludes:

```text
new StarRocks MVs
Slack/email/push
automated stocktake execution
ML forecasting
LLM fine-tuning
```

This matters because it keeps the architecture simpler and prevents overbuilding.

### Success Metrics

The key metrics:

```text
verdict accuracy >= 70%
latency < 10s
citation coverage = 100%
pilot = 1 dark store, >= 1 week
```

For Phase 1, the most relevant metric is:

```text
verdict accuracy >= 70%
```

The deterministic algorithm must be good enough to match analysts at least 70%
of the time.

## File 3: `docs/deliverables/LLD/03-verdict-algorithm.md`

### Purpose

This is the low-level design for the verdict algorithm.

It explains the SQL shape, parameters, output row structure, endpoint, and key
technical decisions.

This is the most technical Phase 1 file.

### SQL Overview

The SQL has four logical parts:

1. `inf`
2. `bin_sum`
3. `fsn_sum`
4. final `SELECT` with `CASE`

### Part 1: `inf`

The `inf` CTE selects relevant INF rows:

```sql
WITH inf AS (
    SELECT reservation_warehouse_id AS wh,
           picklist_source_location_label AS bin,
           picklist_item_fsn AS fsn,
           COUNT(*) AS failures,
           COUNT(DISTINCT order_id) AS orders
    FROM pendency_mv
    WHERE irt_ticket_id IS NOT NULL
      AND updated_at >= NOW() - INTERVAL %(window_days)s DAY
    GROUP BY 1, 2, 3
)
```

Beginner translation:

```text
Take rows from pendency_mv.
Keep only rows that have an IRT ticket.
Keep only rows from the selected time window.
Group by warehouse, BIN, and FSN.
Count failures and impacted orders.
```

This produces one row per:

```text
warehouse + BIN + FSN
```

### Part 2: `bin_sum`

```sql
bin_sum AS (
  SELECT wh, bin, COUNT(DISTINCT fsn) AS distinct_fsns
  FROM inf
  GROUP BY 1, 2
)
```

Beginner translation:

```text
For each warehouse and BIN,
count how many different FSNs failed there.
```

This supports the phantom inventory rule.

### Part 3: `fsn_sum`

```sql
fsn_sum AS (
  SELECT wh, fsn, COUNT(DISTINCT bin) AS distinct_bins
  FROM inf
  GROUP BY 1, 2
)
```

Beginner translation:

```text
For each warehouse and FSN,
count how many different BINs it failed across.
```

This supports the genuine stockout rule.

### Part 4: Final Verdict `CASE`

```sql
CASE
    WHEN b.distinct_fsns >= %(phantom_thr)s
     AND f.distinct_bins >= %(stockout_thr)s THEN 'DUAL'
    WHEN b.distinct_fsns >= %(phantom_thr)s THEN 'PHANTOM_INVENTORY'
    WHEN f.distinct_bins >= %(stockout_thr)s THEN 'GENUINE_STOCKOUT'
    ELSE 'AMBIGUOUS'
END AS verdict
```

Beginner translation:

```text
If both patterns are strong, verdict is DUAL.
Else if the BIN has many different FSN failures, verdict is PHANTOM_INVENTORY.
Else if the FSN failed across many BINs, verdict is GENUINE_STOCKOUT.
Else verdict is AMBIGUOUS.
```

### Parameters

| Parameter | Default | Meaning |
|---|---:|---|
| `window_days` | 1 | How many recent days to inspect. |
| `phantom_thr` | 3 | Distinct FSNs needed for phantom inventory. |
| `stockout_thr` | 2 | Distinct BINs needed for genuine stockout. |

These are configurable through environment variables later.

### Recovery Projection

The LLD also defines:

```text
recovery_pct = orders_impacted(bin, fsn) / total_orders_impacted_in_warehouse * 100
```

This does not decide the verdict.

It helps rank impact:

```text
If we fix this cluster, what percentage of impacted orders might recover?
```

### DiagnosisRow

The output row contains:

```text
warehouse_id
bin
fsn
failures
orders_impacted
distinct_fsns
distinct_bins
verdict
recovery_pct
graph_signals
```

In Phase 1, focus on:

```text
distinct_fsns
distinct_bins
verdict
```

The graph field becomes important later.

## Phase 1 Runtime Example

Input INF rows:

```text
WH-BLR-001, BIN-A, FSN-1
WH-BLR-001, BIN-A, FSN-2
WH-BLR-001, BIN-A, FSN-3
```

Step 1: group into `inf`.

```text
BIN-A + FSN-1
BIN-A + FSN-2
BIN-A + FSN-3
```

Step 2: compute `bin_sum`.

```text
BIN-A has 3 distinct FSNs
```

Step 3: compute `fsn_sum`.

```text
Each FSN appears in 1 BIN
```

Step 4: apply verdict rules.

```text
distinct_fsns = 3
distinct_bins = 1
```

Verdict:

```text
PHANTOM_INVENTORY
```

Reason:

```text
The BIN has many different FSNs failing.
```

Action:

```text
Stocktake BIN-A.
```

## Phase 1 Takeaways

1. The core verdict is deterministic.
2. The verdict is based on two counts: `distinct_fsns` and `distinct_bins`.
3. `distinct_fsns >= 3` points to phantom inventory.
4. `distinct_bins >= 2` points to genuine stockout.
5. If both are true, the verdict is `DUAL`.
6. If neither is true, the verdict is `AMBIGUOUS`.
7. The LLM does not decide the primary verdict.
8. Graph signals add evidence later, but the base rule comes first.
