# Phase 2 Important Technical Decisions

This file captures the key data-model decisions in Phase 2.

## Graph Database Choice: NebulaGraph Vs Neo4j

The project uses NebulaGraph, but Neo4j is a realistic alternative.

Both can model the project's warehouse relationships:

```text
FSN -> FAILED_AT -> BIN
Picker -> ASSIGNED_TO -> BIN
FSN -> RECEIVED_IN -> GRN -> PUTAWAY_TO -> BIN
BIN -> STOCKTAKE -> Variance
```

### Main Difference

```text
Neo4j      = mature, developer-friendly graph database with Cypher
NebulaGraph = distributed graph database designed for large graph workloads
```

### Neo4j

Neo4j uses the Cypher query language.

Example style:

```cypher
MATCH (f:FSN)-[:RECEIVED_IN]->(g:GRN)-[:PUTAWAY_TO]->(b:BIN)
RETURN f, g, b
```

Neo4j strengths:

```text
excellent documentation
easy local development
readable query language
strong visualization tooling
large community
mature ecosystem
```

Neo4j would likely be easier for a beginner or for a graph-heavy product where
interactive exploration and visualization are important.

### NebulaGraph

NebulaGraph uses nGQL and has a more distributed-system-oriented architecture.

In this repo, NebulaGraph runs as multiple services:

```text
nebula-metad
nebula-storaged
nebula-graphd
```

NebulaGraph strengths:

```text
built for large distributed graph workloads
separates query, storage, and metadata services
good fit for high-scale relationship traversal
works with the prescribed project stack
```

### Comparison

| Area | Neo4j | NebulaGraph |
|---|---|---|
| Query language | Cypher | nGQL |
| Beginner friendliness | Usually easier | More complex |
| Ecosystem | Very mature | Smaller |
| Visualization tools | Strong | Less beginner-friendly |
| Local setup | Usually simpler | More moving services |
| Distributed design | Available in enterprise/cluster setups | Central to the architecture |
| Best fit | Learning, graph apps, rich tooling | Large-scale graph traversal workloads |
| Fit for this repo | Could work | Chosen/prescribed stack |

### Why NebulaGraph Is Justified Here

NebulaGraph is justified in this repo because:

```text
the project stack specifies NebulaGraph
the repo already contains NebulaGraph schema and Docker Compose services
the required signals need multi-hop relationship queries
the warehouse domain maps cleanly to nodes and edges
```

Best explanation:

```text
Neo4j would likely be easier for development and visualization because of
Cypher and mature tooling. NebulaGraph is more distributed-system oriented and
can be better for very large graph workloads, but it adds operational
complexity. For this repo, NebulaGraph is mainly justified because it was part
of the prescribed stack and supports the required multi-hop relationship
queries.
```

## Why StarRocks was used for both
pendency_mv belongs in StarRocks because the diagnosis needs SQL aggregation:
count distinct FSNs per BIN
count distinct BINs per FSN
recommendation_log is different. It is not raw warehouse source data. It is system-owned feedback data.
It was likely kept in StarRocks because:
1. StarRocks is already running.
2. Feedback rows are simple structured records.
3. The backend can use one SQL connection style.
4. Demo setup stays smaller.
5. It is easy to join/compare recommendations with failure counts later.

So this is a practical/simple choice, not the only possible design.
Where else could recommendation_log live?
Option	            Why use it	                             Trade-off
PostgreSQL/MySQL	Better fit for transactional app data	Adds another database
SQLite	            Very simple local demo	                Not ideal for multi-user/prod
MongoDB	            Flexible document shape	                Less natural for SQL comparisons
Separate service/storage	Cleaner ownership	            More infrastructure
StarRocks	        Already available, easy analytics	    Not ideal as primary transactional app DB

### Best production answer
In production, I would usually store recommendation_log in a transactional database like PostgreSQL or MySQL.
Why?
Because recommendation lifecycle updates are transactional app events:
suggested -> acknowledged -> executed -> verified
That is more **OLTP**-style data.
StarRocks is more **OLAP**-style:
large analytical scans
aggregations
dashboards
So:
pendency_mv -> StarRocks makes strong sense
recommendation_log -> StarRocks is acceptable for demo, but PostgreSQL/MySQL may be cleaner in production



## Decision 1: Use `pendency_mv` As The Source Table

### Choice

Read INF-like event data from:

```text
hl_customer_outbound.pendency_mv
```

### Why

This matches the project guardrail and problem statement. The project should not
invent a new analytics source for the core verdict.

### Trade-Off

The system depends on the quality and completeness of this source. If important
fields are missing or stale, verdicts and graph signals may be weaker.

## Decision 2: Create A Demo Table Instead Of A New StarRocks MV

### Choice

For local demo, create `pendency_mv` as a base table.

### Why

Production already has the source. The local demo needs somewhere to load fake
data.

This still respects the guardrail:

```text
No new StarRocks materialized views.
```

### Trade-Off

The local table is only a demo mirror. It may not perfectly represent production
behavior.

## Decision 3: Use `DUPLICATE KEY` For `pendency_mv`

### Choice

Use:

```text
DUPLICATE KEY(warehouse, bin, fsn)
```

### Why

The same warehouse + BIN + FSN can fail multiple times.

A unique key would lose repeated failures or reject valid rows.

### Trade-Off

Duplicate data must be aggregated carefully later. This is acceptable because
the diagnosis algorithm explicitly counts and groups rows.

## Decision 4: Add Demo `grn_id` Directly To `pendency_mv`

### Choice

Add:

```text
grn_id
```

directly in the demo table.

### Why

This makes the shared-GRN graph signal easy to demonstrate without adding more
tables or joins.

### Trade-Off

In production, GRN may need to come from another inventory/inbound source. The
design doc already marks this as a clarification.

## Decision 5: Use `recommendation_log` For Closed-Loop Feedback

### Choice

Store recommendations and outcomes in:

```text
recommendation_log
```

### Why

The system needs to show:

```text
recommendation -> action -> result
```

This supports auditability and proof that the system's recommendations helped.

### Trade-Off

This adds one system-owned table. It is allowed because it is not a new
StarRocks materialized view and does not replace the source table.

## Decision 6: Use Compound BIN Vertex IDs

### Choice

Represent BIN graph IDs as:

```text
warehouse_id:bin_label
```

Example:

```text
WH-BLR-001:BIN-A
```

### Why

The same BIN label might exist in multiple warehouses.

Using only:

```text
BIN-A
```

could incorrectly merge two different physical locations.

### Trade-Off

Graph IDs become slightly longer, but correctness is better.

## Decision 7: Keep Graph Replica Factor At 1 For Demo

### Choice

Use:

```text
replica_factor = 1
```

### Why

This is a local Docker demo. One replica is simpler and requires fewer storage
containers.

### Trade-Off

This is not production-grade high availability. A production graph cluster would
need stronger replication.

## Decision 8: Seed Deterministic Demo Scenarios

### Choice

Use crafted scenarios instead of purely random data.

### Why

The demo must prove specific behaviors:

```text
phantom
genuine stockout
dual
picker concentration
shared GRN
ambiguous noise
closed-loop feedback
```

### Trade-Off

Crafted demo data may look cleaner than real warehouse data. Real data will have
more noise and edge cases.

## Decision 9: Separate One-Time Seed Data From Continuous Event Generation

### Choice

Use two different scripts:

```text
data/generate_dummy_data.py -> one-time deterministic demo seed
data/data_generator.py      -> continuous/live event generator
```

### Why

They solve different problems.

`generate_dummy_data.py` creates a predictable dataset with known ground-truth
scenarios:

```text
phantom
genuine stockout
dual
picker-driven
shared GRN
ambiguous/noise
```

This is useful for demos, smoke tests, and learning because the expected result
is known.

`data_generator.py` simulates ongoing warehouse activity by generating batches
on an interval.

Default:

```text
one batch every 2 seconds
```

Custom:

```bash
python data/data_generator.py --interval 5
```

### Why `BASE_DT = now - 6 hours` Exists

The one-time seed script starts timestamps around:

```text
current time - 6 hours
```

The diagnosis default window is:

```text
last 1 day
```

So seeded rows are recent enough to appear in diagnosis results immediately.

### Trade-Off

The split is useful, but it creates two modes that learners must not confuse:

```text
one-time seed != continuous live generator
```

Also, the continuous generator references `inventory_items` in some event types,
while the Phase 2 schema creates only:

```text
pendency_mv
recommendation_log
```

So the continuous generator may need extra schema support or adjustment before
every event type works cleanly.
