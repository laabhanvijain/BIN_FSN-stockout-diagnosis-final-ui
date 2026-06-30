# Phase 6 Technical Decisions

## Decision 1: Keep StarRocks As The Verdict Source

The project does not use NebulaGraph as the main verdict engine.

The verdict comes from StarRocks because StarRocks is better for counting rows quickly.

Examples:

- Count distinct FSNs in one BIN.
- Count distinct BINs for one FSN.
- Count failed orders.

These are SQL aggregation problems.

So the decision is:

```text
StarRocks = verdict source
NebulaGraph = explanation/enrichment source
```

## Decision 2: Use Graph For Relationships

NebulaGraph is used because root cause often depends on relationships.

Examples:

- Same picker repeatedly assigned to the failing BIN.
- Multiple FSNs in the BIN came from the same GRN.
- A stocktake was already done on the BIN.

These are relationship questions, and graph databases are built for relationship traversal.

## Decision 3: Graph Signals Are Additive

Graph signals should improve the answer, but they should not block the system.

If NebulaGraph is unavailable, the SQL verdict can still work.

This is important because warehouse operators should still get a useful answer even if graph enrichment is temporarily down.

## Decision 4: Query Graph Dynamically In Current Code

Older design precomputed graph signals for every diagnosis row.

Current design after Ollama migration queries graph dynamically through the assistant.

Why this is useful:

- The assistant can ask only the graph question it needs.
- Different user questions can trigger different graph traversals.
- It avoids doing graph work for every table row upfront.

Trade-off:

- Assistant answers may be slightly slower because graph is queried during the conversation.
- `/api/diagnoses` no longer directly shows graph signals in every row.

## Decision 5: Cap Query Results

Both StarRocks and NebulaGraph tool execution cap rows at 50.

Why:

- Keeps LLM context smaller.
- Prevents huge responses.
- Reduces latency.
- Makes citations easier to inspect.

## Decision 6: Validate nGQL Before Running

`agent.py` calls:

```python
guards.validate_ngql(ngql)
```

before executing a graph query.

This protects the system from unsafe or unwanted graph operations.

The assistant should run read-only graph queries, not destructive changes.

## Decision 7: Use Citations For Every Claim

Graph query results are added to `citations`.

This matters because the assistant should not say:

```text
This is picker-driven.
```

unless it has actual evidence from a tool result.

Correct style:

```text
Picker PKR-123 appears in most assignment edges for this BIN [c2].
```

## Decision 8: ATP Proxy Is Clearly A Stub

`get_atp_proxy()` is not a real ATP service call.

It assumes:

```text
if one FSN fails in many BINs, ATP is likely zero
```

This is acceptable for demo reasoning, but production should query a real inventory or ATP service.

## Decision 9: Documentation Drift Must Be Noted

Some older docs still mention `enrich_signals()` and `graph_signals` being attached to diagnoses.

Current code says graph signals are queried dynamically by the LLM agent.

As a senior engineer, this matters because documentation can become stale after migrations.

The correct current understanding is:

```text
/diagnoses = deterministic SQL rows
/ask = SQL + graph tool-calling explanation
```
