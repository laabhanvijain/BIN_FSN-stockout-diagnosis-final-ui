# Phase 6 Correct Answers

## 1. What does picker concentration try to detect?

Picker concentration tries to detect whether many failures in the same BIN are connected to one dominant picker.

If one picker accounts for most of the assignments or failures for that BIN, then the issue may be picker-driven. The inventory may not necessarily be wrong; the picker may be repeatedly missing the item, looking in the wrong place, or following a bad process.

## 2. What does shared GRN try to detect?

Shared GRN tries to detect whether multiple failing FSNs in the same BIN came from the same inbound batch.

If all failing FSNs are connected to one GRN, then the root cause may be related to receiving, putaway, or an inbound batch issue.

## 3. Why can two rows have the same SQL verdict but different graph explanations?

Two rows can have the same SQL verdict because their count patterns are the same, but their relationships can be different.

Example:

Both rows may be `PHANTOM_INVENTORY` because many FSNs failed in one BIN.

But one BIN may have failures concentrated under one picker, while another BIN may have failures connected to one shared GRN batch.

So the verdict is the same, but the operational explanation is different.

## 4. Is the graph the source of truth or an enrichment layer?

In this project, the graph is an enrichment layer.

StarRocks is the main source for deterministic verdict counts.

NebulaGraph adds relationship context so the assistant can explain possible root causes more clearly.

## 5. What happens if the graph is unavailable?

The system should still return the SQL verdict.

Graph signals are additive. If NebulaGraph is unavailable or a graph query fails, the system should not crash or block the diagnosis.

The answer may have less context, but the core verdict can still come from StarRocks.

## 6. Explain: SQL tells us what pattern happened; graph tells us what relationships may explain that pattern.

SQL counts the failures and classifies the pattern.

For example:

- many FSNs in one BIN means phantom inventory
- one FSN in many BINs means genuine stockout

Graph then looks at relationships around those failures.

For example:

- Are the failures connected to one picker?
- Are the FSNs connected to one GRN?
- Was stocktake already done?

So SQL gives the main diagnosis, and graph gives richer root-cause evidence.
