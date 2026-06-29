# Phase 1 Correct Answers

These are clean reference answers for the Phase 1 checkpoint questions.

## 1. If Five Different FSNs Fail In One BIN, What Verdict Is Likely And Why?

The likely verdict is:

```text
PHANTOM_INVENTORY
```

Reason:

```text
Many distinct FSNs are failing in the same physical BIN.
```

This makes the BIN suspicious. The system may believe inventory exists there,
but physically the items may be missing, misplaced, stolen, or incorrectly
recorded.

Recommended action:

```text
Stocktake the BIN.
```

## 2. If One FSN Fails In Three Different BINs, What Verdict Is Likely And Why?

The likely verdict is:

```text
GENUINE_STOCKOUT
```

Reason:

```text
The same FSN is failing across multiple distinct BINs.
```

This makes the FSN/product suspicious, not just one location. It suggests the
item may truly be depleted across the warehouse.

Recommended action:

```text
Replenish the FSN.
```

## 3. When Do We Call A Diagnosis DUAL?

The diagnosis is called:

```text
DUAL
```

when both patterns are active at the same time:

```text
distinct_fsns >= 3
AND
distinct_bins >= 2
```

Meaning:

```text
The BIN has many different FSNs failing,
and the same FSN also fails across multiple BINs.
```

This suggests both a BIN-level and FSN-level issue may exist.

## 4. Why Is AMBIGUOUS Better Than Forcing A Verdict?

`AMBIGUOUS` is better because weak evidence should not produce a confident
operational recommendation.

If the system forces a verdict when counts are too low, it may recommend the
wrong action:

```text
wrong stocktake
wrong replenishment
wasted operations effort
lower trust in the system
```

`AMBIGUOUS` means:

```text
There is not enough evidence yet.
Investigate more before taking strong action.
```

## 5. Why Does The Project Use Deterministic Rules Before Graph/LLM Reasoning?

The project uses deterministic rules first because the base verdict must be:

- explainable
- auditable
- predictable
- easy to compare with analyst judgment
- grounded in visible counts

For example, the system can say:

```text
This is PHANTOM_INVENTORY because 5 distinct FSNs failed in the same BIN.
```

That is clearer than an opaque model prediction.

Graph and LLM are still useful, but they are additive:

```text
SQL verdict = foundation
Graph signals = extra evidence
LLM assistant = explanation layer
```

The LLM should explain and investigate using evidence. It should not be the
primary source of the verdict.
