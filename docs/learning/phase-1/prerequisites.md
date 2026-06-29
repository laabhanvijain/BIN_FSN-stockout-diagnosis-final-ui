# Phase 1 Prerequisites

Phase 1 is about warehouse domain rules and the deterministic verdict algorithm.
Before reading the code, you need three simple ideas:

1. Basic counting
2. Grouping by item or location
3. Rule-based classification

## 1. Basic Counting

Counting means asking:

```text
How many things happened?
```

Example INF events:

```text
BIN-A, FSN-1 failed
BIN-A, FSN-2 failed
BIN-A, FSN-3 failed
```

There are 3 failure rows.

But diagnosis usually does not only care about total rows. It cares about
distinct values.

## 2. Distinct Counting

Distinct means unique.

Example:

```text
BIN-A, FSN-1 failed
BIN-A, FSN-1 failed
BIN-A, FSN-2 failed
```

Total failures:

```text
3
```

Distinct FSNs:

```text
2
```

because `FSN-1` appears twice but only counts once as a unique FSN.

This matters because the phantom inventory rule looks for many different FSNs
failing in the same BIN.

## 3. Grouping

Grouping means collecting rows that share the same value.

Example: group by BIN.

```text
BIN-A, FSN-1 failed
BIN-A, FSN-2 failed
BIN-B, FSN-9 failed
```

Grouped by BIN:

```text
BIN-A -> FSN-1, FSN-2
BIN-B -> FSN-9
```

Now we can ask:

```text
How many distinct FSNs failed in each BIN?
```

For the example:

```text
BIN-A -> 2 distinct FSNs
BIN-B -> 1 distinct FSN
```

## 4. Grouping By FSN

We can also group by item/product instead of location.

Example:

```text
BIN-A, FSN-X failed
BIN-B, FSN-X failed
BIN-C, FSN-X failed
BIN-A, FSN-Y failed
```

Grouped by FSN:

```text
FSN-X -> BIN-A, BIN-B, BIN-C
FSN-Y -> BIN-A
```

Now we can ask:

```text
How many distinct BINs did each FSN fail across?
```

For the example:

```text
FSN-X -> 3 distinct BINs
FSN-Y -> 1 distinct BIN
```

This matters because the genuine stockout rule looks for the same FSN failing
across many different BINs.

## 5. Rule-Based Classifier

A classifier assigns a label.

In this project, the label is called a verdict.

The verdicts are:

```text
PHANTOM_INVENTORY
GENUINE_STOCKOUT
DUAL
AMBIGUOUS
```

A rule-based classifier uses fixed rules instead of machine learning.

Example:

```text
IF distinct_fsns >= 3
THEN PHANTOM_INVENTORY
```

This project intentionally uses deterministic rules because the diagnosis must
be explainable, auditable, and aligned with the project spec.

## 6. Threshold

A threshold is a cutoff.

Example:

```text
distinct_fsns >= 3
```

Here, `3` is the threshold.

It means:

```text
If 3 or more different FSNs fail in the same BIN, mark the BIN as suspicious.
```

The project uses two key thresholds:

| Threshold | Default | Meaning |
|---|---:|---|
| `phantom_fsn_threshold` | 3 | How many distinct FSNs must fail in one BIN for phantom inventory. |
| `stockout_bin_threshold` | 2 | How many distinct BINs one FSN must fail across for genuine stockout. |

## 7. Time Window

The diagnosis is not computed over all history forever.

It uses a time window.

Default:

```text
last 1 day
```

That means the system asks:

```text
Within the last 1 day, what failure patterns do we see?
```

This prevents very old failures from incorrectly affecting today's diagnosis.

## 8. Phase 1 Mental Model

Phase 1 is basically:

```text
Take INF events
  -> group them by BIN
  -> count distinct FSNs per BIN
  -> group them by FSN
  -> count distinct BINs per FSN
  -> apply threshold rules
  -> produce verdict
```

The important thing:

```text
No LLM is needed to make the core verdict.
```

The LLM can explain, investigate, and cite evidence later. But the main verdict
comes from deterministic counting rules.
