# Phase 6 Prerequisites: Knowledge Graph Signals

Phase 6 is about understanding why the project uses NebulaGraph after StarRocks.

StarRocks tells us the failure pattern. NebulaGraph helps explain the possible reason behind that pattern.

In simple words:

- StarRocks answers: What happened?
- NebulaGraph answers: What relationships around this BIN, FSN, picker, or GRN may explain why it happened?

## Graph Database Basics

A graph database stores information as vertices and edges.

A vertex is an object.

Examples in this project:

- FSN
- BIN
- Picker
- GRN
- Order
- Variance

An edge is a relationship between two objects.

Examples:

```text
FSN -> FAILED_AT -> BIN
Picker -> ASSIGNED_TO -> BIN
FSN -> RECEIVED_IN -> GRN
BIN -> STOCKTAKE -> Variance
```

A graph traversal means walking through these relationships.

Example:

```text
FSN -> FAILED_AT -> BIN
FSN -> RECEIVED_IN -> GRN
```

This means:

The FSN failed at a BIN, and that same FSN was received through a GRN batch.

## Multi-Hop Relationship

A single-hop relationship has one edge.

Example:

```text
Picker -> BIN
```

A multi-hop relationship has more than one edge or combines multiple patterns.

Example:

```text
FSN -> BIN
FSN -> GRN
```

This helps us answer deeper questions such as:

- Are many failing FSNs connected to the same GRN?
- Are many failures connected to one picker?
- Was a stocktake already done on this BIN?

## Root-Cause Signal

A signal is not the final verdict. It is supporting evidence.

Example:

SQL may say:

```text
PHANTOM_INVENTORY
```

Graph may add:

```text
All failures are connected to one picker.
```

That does not erase the SQL verdict, but it changes the explanation. The issue may be picker-driven rather than pure inventory mismatch.

## Evidence Vs Verdict

The verdict is the main classification:

```text
PHANTOM_INVENTORY
GENUINE_STOCKOUT
DUAL
AMBIGUOUS
```

The verdict comes from StarRocks SQL counts.

Graph signals are extra evidence.

Examples:

- Picker concentration: maybe picker error.
- Shared GRN: maybe inbound batch issue.
- Stocktake done: maybe action already happened.
- ATP proxy: maybe item is genuinely depleted.

So remember:

```text
SQL decides the main verdict.
Graph improves the explanation.
```

## ATP Proxy

ATP means Available To Promise.

In warehouse and inventory systems, ATP is the quantity of an item that the business can confidently promise to customers.

Simple example:

```text
FSN-A total physical quantity = 10
5 units are already reserved for existing orders
ATP = 5
```

So ATP is not always the same as physical quantity. It usually means:

```text
available stock after reservations, holds, and business rules
```

If ATP is 0, the system should usually not promise that item to new customers.

## Why This Project Mentions ATP

For genuine stockout, we want to know whether the FSN is truly unavailable.

If the same FSN is not found in many BINs, that is a strong clue that the item may really be depleted.

Example:

```text
FSN-123 failed in BIN-A
FSN-123 failed in BIN-B
FSN-123 failed in BIN-C
```

This pattern suggests:

```text
The item itself may be out of stock, not just missing from one shelf.
```

A real production system would confirm this by asking an inventory or ATP service:

```text
What is the current ATP for FSN-123?
```

If the ATP service says ATP is 0, then genuine stockout becomes much more believable.

## What Proxy Means

A proxy is a substitute signal.

It is not the real source of truth, but it gives a useful approximation when the real source is not available.

In this project, there is no real production ATP service connected. So the code uses a shortcut:

```python
if distinct_bins >= settings.stockout_bin_threshold:
    return {"atp_likely_zero": True}
```

This means:

If the same FSN has failed in enough different BINs, the system assumes ATP is probably zero or low.

The default stockout threshold is 2.

So if one FSN fails in 2 or more BINs, the proxy can say:

```python
{"atp_likely_zero": True}
```

## Why It Is Only A Proxy

The ATP proxy does not actually check live inventory.

It does not know:

- exact current ATP
- exact physical quantity
- reserved quantity
- damaged quantity
- stock blocked for quality checks
- recent replenishment
- real-time inventory service state

It only looks at the failure pattern.

So this is useful for demo reasoning, but it is not strong enough for final production truth.

## Correct Mental Model

Think of it like this:

```text
Real ATP check: I asked the inventory system and it said ATP is 0.
ATP proxy: I did not ask inventory, but the failure pattern strongly suggests ATP may be 0.
```

So the proxy is a clue, not a final proof.

## How It Helps The Diagnosis

If StarRocks says:

```text
distinct_bins >= 2 for the same FSN
```

then the verdict may be:

```text
GENUINE_STOCKOUT
```

The ATP proxy adds supporting explanation:

```text
Because this FSN failed across multiple BINs, ATP is likely zero.
```

That makes the recommendation stronger:

```text
Recommended action: Replenish the FSN.
```

## Production Upgrade

In production, `get_atp_proxy()` should be replaced or supported by a real call to an inventory or ATP service.

Better production flow:

```text
FSN failed across multiple BINs
-> call inventory/ATP service
-> check actual ATP and quantity
-> use real result in assistant reasoning
```

Then the system can say:

```text
ATP is actually 0 according to inventory service.
```

instead of:

```text
ATP is likely 0 based on failure pattern.
```
