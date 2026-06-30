# Phase 6 Code Walkthrough: Knowledge Graph Signals

Files read for this phase:

- `backend/services/graph.py`
- `backend/services/diagnosis.py`
- `backend/services/agent.py`
- `docs/deliverables/LLD/04-graph-signals.md`
- `docs/code-walkthroughs/backend-graph-signals.md`

## Big Picture

Phase 6 adds graph-based context to the diagnosis system.

The core question is:

```text
After SQL classifies the issue, what relationships explain the issue better?
```

For example:

- SQL may show many FSNs failing in one BIN.
- Graph may show all those failures are connected to the same picker.
- That gives a better operational explanation.

## Current Code Vs Older Docs

There is an important code/documentation drift.

Older docs say graph signals are precomputed and attached to every `/api/diagnoses` row as `graph_signals`.

Current code after the Ollama migration does not do that.

Current behavior:

- `/api/diagnoses` returns deterministic SQL diagnosis rows.
- The LLM assistant can query NebulaGraph dynamically using the `query_nebulagraph` tool.

So in the current implementation, graph signals are mostly used by the assistant when answering questions.

## `backend/services/graph.py`

This file contains helper functions for graph signals.

It imports:

```python
from collections import Counter
from backend.config import settings
from backend.db.nebula import get_session
```

`Counter` is used to count picker IDs.

`settings` gives configuration values, such as the NebulaGraph space and thresholds.

`get_session()` gives a NebulaGraph session.

## `_exec(session, ngql)`

This helper executes nGQL.

It prepends:

```ngql
USE <nebula_space>;
```

Then it runs the query.

If the query fails, it logs a warning and returns `None`.

This is important because graph failure should not crash the whole diagnosis system.

## `_bin_vid(wh, label)`

This helper creates a NebulaGraph vertex ID for a BIN.

```python
return f"{wh}:{label}"
```

Example:

```text
WH-BLR-001:BIN-PICKER-A
```

NebulaGraph needs stable vertex IDs so queries can target the exact BIN.

## `get_picker_concentration(wh, bin_label)`

This checks whether one picker dominates failures for a BIN.

The graph query looks like:

```ngql
MATCH (p:Picker)-[:ASSIGNED_TO]->(b:BIN)
WHERE id(b) == "WH:BIN"
RETURN p.Picker.picker_id AS picker_id
```

Then the code:

1. Collects picker IDs.
2. Counts how many times each picker appears.
3. Finds the most common picker.
4. Computes concentration.

Example:

```text
8 failures total
7 connected to PKR-123
concentration = 7 / 8 = 0.875
```

If concentration is at least `0.7`, it returns:

```python
{
  "picker_concentration": 0.875,
  "dominant_picker": "PKR-123"
}
```

Meaning:

The issue may be picker-driven.

## `get_shared_grn(wh, bin_label)`

This checks whether all failing FSNs in a BIN came from the same GRN batch.

The graph pattern is:

```text
FSN -> FAILED_AT -> BIN
FSN -> RECEIVED_IN -> GRN
```

The query returns FSN and GRN pairs.

Then the code collects unique GRN IDs.

If there is exactly one unique GRN, it returns:

```python
{
  "shared_grn": "GRN-SHARED-999",
  "fsn_count": 4
}
```

Meaning:

The issue may be related to one inbound receiving batch.

## `get_stocktake_done(wh, bin_label)`

This checks whether a stocktake was already done for the BIN.

The graph pattern is:

```text
BIN -> STOCKTAKE -> Variance
```

If such an edge exists, it returns:

```python
{"stocktake_done": True}
```

Meaning:

Someone may already have audited the BIN.

## `get_atp_proxy(distinct_bins)`

This is not truly a graph query.

It is a conservative shortcut.

If one FSN is failing in many BINs, then ATP is probably zero or low.

```python
if distinct_bins >= settings.stockout_bin_threshold:
    return {"atp_likely_zero": True}
```

Meaning:

This supports a genuine stockout explanation.

## `backend/services/diagnosis.py`

This file computes the main verdict using StarRocks SQL.

Current code has this comment:

```python
# Build diagnosis rows (graph signals now queried dynamically by LLM agent)
```

That means graph signals are no longer attached directly to every diagnosis row.

The diagnosis response focuses on:

- warehouse ID
- BIN
- FSN
- failures
- orders impacted
- distinct FSNs
- distinct BINs
- verdict
- recovery percentage

## `backend/services/agent.py`

This file connects Phase 6 graph logic to the LLM assistant.

The assistant gets two tools:

```python
query_starrocks
query_nebulagraph
```

`query_starrocks` is for SQL counts and warehouse facts.

`query_nebulagraph` is for graph relationship queries.

## `_execute_nebulagraph(ngql, warehouse_id)`

This function:

1. Validates the nGQL query.
2. Opens a NebulaGraph session.
3. Prepends `USE <space>;`.
4. Executes the query.
5. Converts NebulaGraph rows into Python dictionaries.
6. Returns a citation-ready result.

The result shape is:

```python
{
  "ok": True,
  "engine": "nebulagraph",
  "query": ngql,
  "row_count": len(rows),
  "rows": rows,
}
```

This is important because every factual assistant claim must be backed by a citation.

## Example Runtime Flow

User asks:

```text
Why is BIN-PICKER-A failing?
```

The assistant should:

1. Query StarRocks for failure counts.
2. Query NebulaGraph for picker relationships.
3. Find whether one picker dominates the failures.
4. Combine both pieces of evidence.
5. Give a cited answer.

Example reasoning:

```text
SQL says many FSNs failed in one BIN, so the deterministic verdict may be PHANTOM_INVENTORY.
Graph says most failures are linked to one picker, so the operational explanation may be picker-driven.
```

## What To Skim

In `agent.py`, many helper functions exist for fallback behavior, SQL extraction, hallucination detection, and answer synthesis.

For Phase 6, focus mainly on:

- `TOOL_SPECS`
- `_execute_nebulagraph`
- `execute_tool`
- `_run_tool`
- `ask`

The other fallback helpers are more relevant to Phase 7.
