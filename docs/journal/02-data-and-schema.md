# 02 · Data & Schema

> Schemas (StarRocks + NebulaGraph) and dummy data generation notes.
> Milestones: M2 (schema), M3 (dummy data). Detail: [../deliverables/LLD/02-data-schemas.md](../deliverables/LLD/02-data-schemas.md).

---

## 2026-06-25 — M3 complete: dummy data generator (6 ground-truth scenarios)

### What was done

**`data/generate_dummy_data.py`** — reproducible seed (fixed `random.seed(42)`).

Six scenarios seeded into `pendency_mv`:

| Scenario | BIN / FSN | INF rows | Expected verdict | Extra signal |
|----------|-----------|----------|-----------------|--------------|
| S1 PHANTOM | BIN-PHANTOM-A, 5 FSNs | 10 | PHANTOM_INVENTORY | — |
| S2 GENUINE | FSN-S2-001, 3 BINs | 9 | GENUINE_STOCKOUT | — |
| S3 DUAL | BIN-DUAL-A 4 FSNs + FSN-S3-001 in 2 more BINs | 6 | DUAL | — |
| S4 PICKER | BIN-PICKER-A, 4 FSNs, all picker=PKR-BAD | 8 | PHANTOM + picker_concentration=1.0 | graph: picker signal |
| S5 SHARED_GRN | BIN-GRN-A, 4 FSNs, all grn=GRN-SHARED-999 | 4 | PHANTOM + shared_grn flag | graph: GRN signal |
| S6 NOISE | BIN-NOISE-1/2, 1 FSN each | 2 | AMBIGUOUS | — |

Two pre-resolved `recommendation_log` rows (status=`verified`) show the closed-loop
delta in the Feedback UI (`failures_before=10 → failures_after=0` and `9 → 1`).

### Technical decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fixed random seed (42) | `random.seed(42)` | Reproducible demo every run |
| `--clear` flag | Optional, not default | Safe to re-run without data loss unless explicitly clearing |
| S4/S5 SQL verdict still PHANTOM | Intentional | Graph signals are additive enrichments; SQL verdict is the base layer |
| Ground-truth dict (`EXPECTED_VERDICTS`) | Inline dict | Used for accuracy measurement without extra files |
| `recommendation_log` rows pre-seeded | 2 verified rows | Demo the closed-loop Feedback UI without running through the whole flow |

### Files created

- `data/generate_dummy_data.py`

### Status: committed 2026-06-25

---

## 2026-06-25 — M2 complete: schema DDL (StarRocks + NebulaGraph)

### What was done

**`data/schema/starrocks.sql`**
- `CREATE DATABASE IF NOT EXISTS hl_customer_outbound` — mirrors the real WMS
  database name exactly so no connection-string changes are needed.
- `pendency_mv` table: DUPLICATE KEY on `(wh, bin, fsn)`, distributed by
  `HASH(reservation_warehouse_id)`, `replication_num=1` for the local demo.
  Includes all PS-prescribed columns plus `grn_id` (demo-only for the
  shared-inbound-batch graph signal).
- `recommendation_log` table: `AUTO_INCREMENT` primary key `id`, lifecycle
  status column (`suggested|acknowledged|executed|verified`), `failures_before`
  and `failures_after` for closed-loop delta computation, `evidence_ref TEXT`
  for cited query strings.

**`data/schema/nebula.ngql`**
- Space `stockout` created: `partition_num=10`, `replica_factor=1`, `FIXED_STRING(128)` VIDs.
- Tags: `FSN`, `BIN`, `Picker`, `Order`, `GRN`, `Variance`.
- 6 edge types: `FAILED_AT`, `PICKED_FROM`, `ASSIGNED_TO`, `RECEIVED_IN`,
  `PUTAWAY_TO`, `STOCKTAKE`.
- Tag indexes on every key lookup property (32-char prefix); `REBUILD TAG INDEX`
  called immediately.

### Technical decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| BIN VID = `wh_id:label` | Compound | Same BIN label can exist in multiple warehouses; compound VID ensures uniqueness globally |
| StarRocks DUPLICATE KEY (not UNIQUE/AGGREGATE) | DUPLICATE | Multiple INF events per (wh,bin,fsn) are all valid; UNIQUE would drop older events |
| `grn_id` as a column on `pendency_mv` (not a new MV) | Column | PS guardrail: "no new StarRocks MVs"; simpler for the demo |
| `replica_factor=1` | 1 | Local demo on a single Docker host; 3 replicas require 3 storage nodes |
| `Variance` tag in NebulaGraph | Added | Needed to model the STOCKTAKE → Variance closed-loop edge |

### Files created

- `data/schema/starrocks.sql`
- `data/schema/nebula.ngql`
- `data/schema/.gitkeep` (was present; now superseded by real files)

### Status: committed 2026-06-25

<!-- ## YYYY-MM-DD — <what happened> -->
