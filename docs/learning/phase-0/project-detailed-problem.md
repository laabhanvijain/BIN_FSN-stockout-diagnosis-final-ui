# Phase 0 Project Detailed Problem

This file explains the project problem and the overall system in beginner
language.

## What This Project Is

BIN-FSN Stockout Diagnosis is a warehouse diagnosis dashboard.

It helps answer:

```text
What failed?
Where did it fail?
Is the BIN suspicious?
Is the FSN truly out of stock?
What evidence supports that?
What action should the operator take?
Did the action work?
```

The project diagnoses warehouse pick failures into actionable root causes.

## The Warehouse Situation

In a warehouse, a picker may be told:

```text
Go to BIN F1-05-5D and pick item FSN123.
```

But when the picker reaches the BIN, the item is not there.

That event is called an INF:

```text
INF = Item Not Found
```

The business problem is:

```text
The system knows something failed, but people still need to figure out why.
```

Manual diagnosis can take days because an analyst may need to check many
dashboards, tables, tickets, and operational records.

This project tries to reduce that diagnosis time from days to minutes.

## Important Warehouse Terms

| Term | Meaning |
|---|---|
| FSN | Product/item identifier. It answers: which item? |
| BIN | Physical warehouse location. It answers: which shelf/slot/bin? |
| INF | Item Not Found. The picker could not find the item. |
| IRT | Inventory Resolution Ticket created for inventory investigation. |
| Picker | Person/system actor assigned to pick items. |
| GRN | Goods Receipt Note or inbound batch identifier. |
| Stocktake | Physical check/count of inventory in a BIN. |
| Replenish | Bring more stock for an item. |

## The Two Main Root Causes

The project focuses on two important patterns.

## Pattern 1: Many FSNs Failing In One BIN

Example:

```text
BIN-A has failures for:
FSN1
FSN2
FSN3
FSN4
FSN5
```

This suggests the BIN itself is suspicious.

Possible explanation:

- The BIN has bad inventory records.
- Items are misplaced.
- Items are missing.
- The system thinks stock exists, but physically it does not.

Verdict:

```text
PHANTOM_INVENTORY
```

Action:

```text
Stocktake the BIN
```

Meaning: physically check that BIN.

Short memory hook:

```text
BIN problem -> PHANTOM_INVENTORY
```

## Pattern 2: One FSN Failing Across Many BINs

Example:

```text
FSN-X failed in:
BIN-A
BIN-B
BIN-C
```

This suggests the item itself is depleted across the warehouse.

Possible explanation:

- The warehouse truly does not have enough of that item.
- The item may need replenishment.
- The issue is not just one bad BIN.

Verdict:

```text
GENUINE_STOCKOUT
```

Action:

```text
Replenish the FSN
```

Meaning: bring more of that item.

Short memory hook:

```text
FSN problem -> GENUINE_STOCKOUT
```

## The Four Verdicts

| Verdict | Meaning |
|---|---|
| `PHANTOM_INVENTORY` | Many different FSNs failing in the same BIN. |
| `GENUINE_STOCKOUT` | The same FSN failing across many BINs. |
| `DUAL` | Both phantom and stockout patterns appear together. |
| `AMBIGUOUS` | Not enough evidence to confidently classify. |

The simplest way to remember the rule:

```text
BIN pattern -> PHANTOM_INVENTORY
FSN pattern -> GENUINE_STOCKOUT
both patterns -> DUAL
unclear pattern -> AMBIGUOUS
```

## Why `AMBIGUOUS` Matters

The system should not pretend to know something when evidence is weak.

If there is only one failure, or the pattern is not strong enough, forcing a
verdict could mislead operations.

`AMBIGUOUS` means:

```text
There is a signal, but not enough evidence yet.
Investigate more before taking a strong action.
```

## Concrete Example 1: Phantom Inventory

Suppose the system has these failure events:

```text
WH-BLR-001, BIN-A, FSN-1 failed
WH-BLR-001, BIN-A, FSN-2 failed
WH-BLR-001, BIN-A, FSN-3 failed
```

The backend sees:

```text
Same BIN: BIN-A
Different FSNs: 3
```

So it says:

```text
Verdict: PHANTOM_INVENTORY
Reason: many distinct FSNs failed in one BIN
Action: stocktake BIN-A
```

## Concrete Example 2: Genuine Stockout

Suppose the system has these failure events:

```text
WH-BLR-001, BIN-A, FSN-X failed
WH-BLR-001, BIN-B, FSN-X failed
WH-BLR-001, BIN-C, FSN-X failed
```

The backend sees:

```text
Same FSN: FSN-X
Different BINs: 3
```

So it says:

```text
Verdict: GENUINE_STOCKOUT
Reason: the same FSN failed across many BINs
Action: replenish FSN-X
```

## Where The Knowledge Graph Helps

SQL can tell us the main pattern:

```text
How many FSNs failed in this BIN?
How many BINs did this FSN fail across?
```

But the graph can help explain relationships:

```text
Were the failures connected to the same picker?
Were the failed items from the same GRN/inbound batch?
Did a stocktake happen later?
```

Example:

```text
SQL verdict: PHANTOM_INVENTORY
Graph signal: all failures involved picker PKR-BAD
```

That means the SQL verdict is still useful, but the graph adds more context:

```text
Maybe this is not only a bad BIN.
Maybe a picker/process issue is contributing.
```

The graph does not replace the verdict. It enriches the investigation.

## How The Whole System Fits Together

Beginner architecture:

```text
User opens React UI
  -> React asks FastAPI backend for data
  -> FastAPI queries StarRocks for failure counts
  -> FastAPI computes verdict
  -> FastAPI may query NebulaGraph for relationship evidence
  -> FastAPI may ask Ollama LLM to explain with citations
  -> React displays results
```

Or more compactly:

```text
React UI
  -> FastAPI backend
      -> StarRocks for table/counting data
      -> NebulaGraph for relationship data
      -> Ollama for assistant explanation
  -> React displays final answer
```

## What Each Main Folder Means

```text
backend/
```

Server-side Python code. This is where APIs, diagnosis logic, graph queries, LLM
assistant, and feedback logic live.

```text
frontend/
```

Browser UI code. This is what users interact with.

```text
data/
```

Database schemas and demo data generators.

```text
infra/
```

Docker setup, schema initialization, and smoke test scripts.

```text
docs/
```

Documentation, including the beginner learning folder.

```text
design/
```

Architecture and milestone planning docs.

```text
explanation/
```

Extra context about the WMS/domain background.

## The Main Runtime Story

The most important runtime flow is:

```text
User opens diagnosis table
  -> frontend calls GET /api/diagnoses
  -> backend receives the request
  -> backend queries StarRocks
  -> backend counts failures
  -> backend assigns verdict
  -> backend may attach graph signals
  -> frontend displays the result
```

The second important runtime flow is:

```text
User asks assistant a question
  -> frontend calls POST /api/ask
  -> backend sends prompt/tools to Ollama
  -> assistant queries StarRocks or NebulaGraph through tools
  -> answer is generated with citations
  -> frontend displays the answer and evidence
```

The third important runtime flow is:

```text
User logs recommendation
  -> backend stores recommendation in recommendation_log
  -> user advances action status
  -> backend compares failures before and after
  -> UI shows whether failures ceased
```

## What The Project Is Ultimately Trying To Prove

This system is trying to prove that warehouse diagnosis can be:

- faster
- more explainable
- more evidence-based
- more actionable
- easier to audit

Instead of saying:

```text
Something is wrong with inventory.
```

It tries to say:

```text
BIN-PHANTOM-A likely has phantom inventory because 5 distinct FSNs failed there.
Stocktake this BIN.
Here is the evidence.
Here is whether the action worked later.
```

## Phase 0 Takeaways

1. The project diagnoses warehouse pick failures.
2. The main failure event is INF, meaning Item Not Found.
3. FSN means product/item; BIN means physical warehouse location.
4. Many FSNs failing in one BIN usually means phantom inventory.
5. One FSN failing across many BINs usually means genuine stockout.
6. StarRocks handles table/counting logic.
7. NebulaGraph handles relationship evidence.
8. The LLM assistant should explain using citations, not guesses.
9. React shows the UI.
10. FastAPI connects the UI, databases, graph, and LLM.

## Phase 0 Checkpoint Questions

Answer these before moving to Phase 1:

1. What is an INF event?
2. What is the difference between an FSN and a BIN?
3. Why does the project need both a frontend and a backend?
4. Why does the project use StarRocks?
5. Why does the project use NebulaGraph?
6. What does `PHANTOM_INVENTORY` mean?
7. What does `GENUINE_STOCKOUT` mean?

## Phase 0 Exercise

Write a 5-line explanation of the project in your own words.
