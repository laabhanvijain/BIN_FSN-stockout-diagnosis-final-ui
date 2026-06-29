# Phase 1 Important Technical Decisions

This file captures the most important Phase 1 design decisions and why they
matter.

## Decision 1: Use Deterministic Rules As The Core Verdict

### Choice

Use fixed rules:

```text
distinct_fsns >= 3 AND distinct_bins >= 2 -> DUAL
distinct_fsns >= 3                        -> PHANTOM_INVENTORY
distinct_bins >= 2                        -> GENUINE_STOCKOUT
else                                      -> AMBIGUOUS
```

### Why

The project needs:

- explainability
- auditability
- predictable behavior
- alignment with the problem statement
- analyst comparison

If a store operator asks:

```text
Why did you say this is phantom inventory?
```

The system can answer:

```text
Because 3 or more distinct FSNs failed in that BIN.
```

That is easier to trust than an opaque ML score.

### Trade-Off

The rule may be too rigid for some real-world edge cases.

Example:

```text
2 FSNs fail badly in one BIN, but the threshold is 3.
```

The system may mark it as `AMBIGUOUS`, even though an analyst might suspect a
real issue.

The mitigation is:

```text
show raw counts + graph signals + allow human judgment
```

## Decision 2: Keep ML Forecasting Out Of Scope

### Choice

Do not train a forecasting model or custom classifier.

### Why

The project guardrails explicitly exclude ML forecasting. Also, the current
problem is not predicting future demand. It is explaining current/recent INF
failures.

### Trade-Off

The system may not discover subtle patterns that a trained model could learn.

But for this project, explainability is more important than model complexity.

## Decision 3: Use StarRocks For Count-Based Diagnosis

### Choice

Compute the base verdict from SQL-style aggregations.

### Why

The questions are naturally table/count questions:

```text
How many distinct FSNs failed in this BIN?
How many distinct BINs did this FSN fail across?
```

SQL is well suited for this.

### Trade-Off

SQL is less natural for multi-hop relationship questions, such as picker overlap
or shared inbound batches. That is why the project adds NebulaGraph later.

## Decision 4: Treat Graph And LLM As Additive, Not Primary

### Choice

The deterministic SQL verdict stands on its own. Graph and LLM layers enrich or
explain it.

### Why

If NebulaGraph or Ollama is unavailable, the system can still produce a base
diagnosis from StarRocks.

This makes the architecture more robust:

```text
SQL verdict = foundation
graph signals = extra evidence
LLM assistant = explanation layer
```

### Trade-Off

Some richer root causes may only be visible through graph investigation. But the
system still has a useful fallback.

## Decision 5: Use Time Windowed Diagnosis

### Choice

By default, diagnose failures from the last 1 day.

### Why

Recent failures matter most for operational action.

Old failures should not permanently contaminate today's diagnosis.

### Trade-Off

A short window may miss slow-building patterns. A long window may include stale
problems.

The project makes this configurable through `DIAGNOSIS_WINDOW_DAYS`.

## Decision 6: Use `AMBIGUOUS` Instead Of Forcing A Verdict

### Choice

If neither threshold is crossed, return:

```text
AMBIGUOUS
```

### Why

Weak evidence should not produce a confident operational recommendation.

This is safer than pretending every failure has an obvious cause.

### Trade-Off

Some users may want a stronger answer. But an honest ambiguous result protects
against wrong stocktake or replenishment actions.

## Decision 7: Check `DUAL` Before Individual Verdicts

### Choice

The rule checks:

```text
DUAL first
PHANTOM second
GENUINE third
AMBIGUOUS last
```

### Why

If both `distinct_fsns >= 3` and `distinct_bins >= 2` are true, the system should
not hide one signal.

Example:

```text
distinct_fsns = 4
distinct_bins = 3
```

This is both phantom-like and stockout-like. So the verdict should be:

```text
DUAL
```

### Trade-Off

`DUAL` is more complex operationally because it may require both stocktake and
replenishment investigation. But it is more truthful than choosing only one
side.
