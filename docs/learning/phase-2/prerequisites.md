# Phase 2 Prerequisites

Phase 2 is about data storage. Before reading the schema files, understand these
ideas:

1. Table
2. Row
3. Column
4. Schema
5. SQL
6. Graph
7. Vertex/node
8. Edge/relationship
9. Demo data

## 1. Table

A table stores data in rows and columns.

Example:

```text
warehouse_id | bin_label | fsn   | picker
WH-BLR-001   | BIN-A     | FSN-1 | PKR-001
WH-BLR-001   | BIN-A     | FSN-2 | PKR-002
```

In this project, StarRocks stores table data.

## 2. Row

A row is one record/event.

Example:

```text
WH-BLR-001, BIN-A, FSN-1, PKR-001
```

For this project, one row in `pendency_mv` represents a WMS-like pick failure or
pick-related event.

## 3. Column

A column is one field in a row.

Examples:

```text
warehouse_id
bin_label
fsn
picker
updated_at
```

Each column answers one question.

Example:

```text
picklist_item_fsn -> which product?
picklist_source_location_label -> which BIN?
reservation_warehouse_id -> which warehouse?
```

## 4. Schema

A schema defines what data can exist.

It answers:

```text
What tables exist?
What columns exist?
What graph node types exist?
What relationships exist?
```

In this project:

```text
data/schema/starrocks.sql -> table schema
data/schema/nebula.ngql   -> graph schema
```

## 5. SQL

SQL is a language for working with table data.

Example questions SQL can answer:

```text
How many FSNs failed in BIN-A?
How many BINs did FSN-X fail across?
Which recommendations are verified?
```

This project uses StarRocks with SQL-style queries.

## 6. Graph

A graph stores things and relationships between things.

Example:

```text
FSN-1 -> FAILED_AT -> BIN-A
PKR-001 -> ASSIGNED_TO -> BIN-A
GRN-999 -> PUTAWAY_TO -> BIN-A
```

This project uses NebulaGraph for relationship evidence.

## 7. Vertex / Node

A vertex, also called a node, is an entity in a graph.

Project examples:

```text
FSN
BIN
Picker
Order
GRN
Variance
```

Think:

```text
node = thing
```

## 8. Edge / Relationship

An edge connects two nodes.

Project examples:

```text
FSN -> FAILED_AT -> BIN
Picker -> ASSIGNED_TO -> BIN
FSN -> RECEIVED_IN -> GRN
GRN -> PUTAWAY_TO -> BIN
```

Think:

```text
edge = relationship/action between things
```

## 9. Demo Data

Demo data is fake but intentional data used to test and show the system.

This project seeds six scenarios:

```text
S1 phantom inventory
S2 genuine stockout
S3 dual
S4 picker-driven
S5 shared GRN
S6 ambiguous/noise
```

The demo data is not random chaos. It is designed so that each verdict or graph
signal can be clearly demonstrated.

## Phase 2 Mental Model

```text
StarRocks stores the raw/event rows.
NebulaGraph stores relationships derived from those rows.
Dummy data creates known examples so the system can be tested and explained.
```

Simple memory hook:

```text
StarRocks = rows and counts
NebulaGraph = nodes and relationships
Dummy data = known test stories
```
