# Phase 0 Correct Answers

These are clean reference answers for the Phase 0 checkpoint questions. Use them
to compare with your own answers and improve your explanation.

## 1. What Is An INF Event?

An INF event means **Item Not Found**.

It happens when a picker goes to the assigned BIN to pick a specific FSN, but the
item is not physically found there.

In this project, INF events are the main failure signals used for diagnosis.

## 2. What Is The Difference Between An FSN And A BIN?

An **FSN** is the item/product identifier.

It answers:

```text
Which product are we trying to pick?
```

A **BIN** is the physical warehouse location.

It answers:

```text
Where in the warehouse should the picker find the product?
```

Simple memory hook:

```text
FSN = product
BIN = location
```

## 3. Why Does The Project Need Both A Frontend And A Backend?

The project needs a **frontend** because users need a visual interface where they
can see diagnoses, ask assistant questions, and track feedback.

The project needs a **backend** because the frontend should not directly query
databases or run diagnosis logic. The backend receives frontend requests, queries
StarRocks and NebulaGraph, applies business rules, calls the LLM assistant when
needed, and returns structured results to the frontend.

The relationship is:

```text
User
  -> React frontend
  -> FastAPI backend
  -> StarRocks / NebulaGraph / Ollama
  -> FastAPI backend
  -> React frontend
  -> User sees answer
```

## 4. Why Does The Project Use StarRocks?

The project uses StarRocks because the core diagnosis needs table-based
counting and grouping over INF events.

Examples:

```text
How many distinct FSNs failed in this BIN?
How many distinct BINs did this FSN fail across?
```

These are SQL aggregation questions, and StarRocks is used as the analytics
store for those queries.

In this project, StarRocks stores the `hl_customer_outbound.pendency_mv`-shaped
data and the `recommendation_log` table.

## 5. Why Does The Project Use NebulaGraph?

The project uses NebulaGraph because some useful evidence is relationship-based,
not just count-based.

NebulaGraph helps answer questions like:

```text
Are many failures connected to the same picker?
Did failed FSNs share the same GRN/inbound batch?
Is there stocktake-related evidence for a BIN?
```

StarRocks gives the main verdict pattern. NebulaGraph adds context and richer
root-cause evidence.

Simple memory hook:

```text
StarRocks = counts and tables
NebulaGraph = relationships and paths
```

## 6. What Does PHANTOM_INVENTORY Mean?

`PHANTOM_INVENTORY` means the system believes stock exists, but physically the
item may be missing, misplaced, or incorrectly recorded.

In this project, the main pattern is:

```text
Many different FSNs fail in the same BIN
  -> the BIN is suspicious
  -> verdict is PHANTOM_INVENTORY
  -> recommended action is stocktake the BIN
```

## 7. What Does GENUINE_STOCKOUT Mean?

`GENUINE_STOCKOUT` means the item itself appears to be truly unavailable or
depleted across the warehouse.

In this project, the main pattern is:

```text
The same FSN fails across many BINs
  -> the FSN is suspicious
  -> verdict is GENUINE_STOCKOUT
  -> recommended action is replenish the FSN
```

## 8. Five-Line Project Explanation

This project diagnoses warehouse pick failures where a picker cannot find an FSN
in an assigned BIN. The React frontend lets users view diagnosis results, ask an
assistant questions, and track recommendation feedback. The FastAPI backend
queries StarRocks to count failure patterns and classify them as
`PHANTOM_INVENTORY`, `GENUINE_STOCKOUT`, `DUAL`, or `AMBIGUOUS`. NebulaGraph adds
relationship-based evidence such as picker overlap or shared GRN batch. The
Ollama-powered LLM assistant uses SQL and graph evidence to explain the result
with citations and suggest the next action.

## Important Correction

The user usually does **not** manually report a fresh INF through this UI.

Instead, the project mainly reads INF events that already exist in the warehouse
data source. The UI helps users inspect existing failure patterns, ask questions,
log recommendations, and track outcomes.
