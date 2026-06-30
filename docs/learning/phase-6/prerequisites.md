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
