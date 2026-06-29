# data/generate_dummy_data.py — Code Walkthrough

> Source: `data/generate_dummy_data.py`
> Milestone: M3 · Last updated: 2026-06-25

## What it does

Seeds `hl_customer_outbound.pendency_mv` and `recommendation_log` with 6 deterministic
ground-truth scenarios. Every demo run with `--clear` produces the exact same rows
(fixed `random.seed(42)`).

---

## File structure

```
generate_dummy_data.py
├── Constants (WH, BASE_DT, SEED)
├── make_row()          — builds one pendency_mv dict
├── scenario_s1_phantom()  – S1: 5 FSNs × 2 failures in BIN-PHANTOM-A
├── scenario_s2_genuine()  – S2: FSN-S2-001 × 3 failures in 3 BINs
├── scenario_s3_dual()     – S3: 4 FSNs in BIN-DUAL-A + cross-BIN GENUINE signal
├── scenario_s4_picker()   – S4: 4 FSNs all assigned to PKR-BAD
├── scenario_s5_shared_grn() – S5: 4 FSNs all from GRN-SHARED-999
├── scenario_s6_noise()    – S6: 2 isolated single failures
├── recommendation_log_rows() — 2 pre-resolved rows for the Feedback UI demo
├── EXPECTED_VERDICTS       — ground-truth dict for accuracy measurement
└── main()              — CLI: connect → clear? → insert → print summary
```

---

## Scenario breakdown

### S1 — PHANTOM_INVENTORY
- 5 distinct FSNs (`FSN-S1-001` to `FSN-S1-005`) in `BIN-PHANTOM-A`.
- 2 failures per FSN → 10 total rows.
- Same picker (`PKR-001`) and GRN (`GRN-BATCH-001`) — **no** picker/GRN signals triggered
  (they're all from the same batch for simplicity; the signals only trigger when concentration
  is high *relative to* other pickers/GRNs).
- PS SQL: `distinct_fsn_count = 5 >= 3` → **PHANTOM_INVENTORY**.

### S2 — GENUINE_STOCKOUT
- 1 FSN (`FSN-S2-001`) across 3 distinct BINs (`BIN-GENUINE-A/B/C`).
- 3 failures per BIN → 9 total rows.
- Different pickers per BIN to rule out picker signal.
- PS SQL: `distinct_bin_count = 3 >= 2` → **GENUINE_STOCKOUT**.

### S3 — DUAL
- `BIN-DUAL-A`: 4 distinct FSNs → PHANTOM signal.
- `FSN-S3-001` also appears in `BIN-DUAL-B` and `BIN-DUAL-C` → GENUINE signal.
- Both thresholds crossed simultaneously → **DUAL**.

### S4 — PICKER_DRIVEN (base verdict: PHANTOM)
- 4 FSNs in `BIN-PICKER-A`, all `picklist_assigned_to = PKR-BAD`.
- PS SQL sees `distinct_fsn_count = 4` → PHANTOM_INVENTORY.
- Graph ETL will create 4 `ASSIGNED_TO` edges from `PKR-BAD → BIN-PICKER-A`.
- Graph signal `picker_concentration = 1.0` (100% from one picker) → root cause annotation.

### S5 — SHARED_GRN (base verdict: PHANTOM)
- 4 FSNs in `BIN-GRN-A`, all `grn_id = GRN-SHARED-999`.
- PS SQL sees `distinct_fsn_count = 4` → PHANTOM_INVENTORY.
- Graph ETL will create `RECEIVED_IN` (FSN → GRN) and `PUTAWAY_TO` (GRN → BIN) edges.
- Graph signal `shared_grn = GRN-SHARED-999` → root cause annotation.

### S6 — NOISE / AMBIGUOUS
- 2 isolated rows in 2 different BINs, 1 failure each.
- Neither threshold crossed → **AMBIGUOUS**.

---

## `recommendation_log` pre-seed

Two `status=verified` rows are inserted so the **Feedback UI** has data to display
immediately on demo day, without needing to run through the full suggest→execute flow:

| Row | Verdict | `failures_before` | `failures_after` | Closed? |
|-----|---------|-------------------|-----------------|---------|
| BIN-PHANTOM-A / FSN-S1-001 | PHANTOM | 10 | 0 | Yes (failures_ceased=10) |
| BIN-GENUINE-A / FSN-S2-001 | GENUINE | 9 | 1 | Partial (failures_ceased=8) |

---

## `EXPECTED_VERDICTS` dict

```python
EXPECTED_VERDICTS = {
    ("BIN-PHANTOM-A", "*"):   "PHANTOM_INVENTORY",
    ("*", "FSN-S2-001"):      "GENUINE_STOCKOUT",
    ("BIN-DUAL-A", "*"):      "DUAL",
    ("BIN-PICKER-A", "*"):    "PHANTOM_INVENTORY",
    ("BIN-GRN-A", "*"):       "PHANTOM_INVENTORY",
    ("BIN-NOISE-1", "*"):     "AMBIGUOUS",
    ("BIN-NOISE-2", "*"):     "AMBIGUOUS",
}
```

`"*"` means "any FSN" or "any BIN". Used to evaluate verdict accuracy
(`correct_verdicts / total_diagnoses`).

---

## How to run

```bash
# Start StarRocks first
docker compose -f infra/docker-compose.yml up -d starrocks-fe starrocks-be

# Apply schema (once)
mysql -h 127.0.0.1 -P 9030 -u root < data/schema/starrocks.sql

# Seed data (re-runnable; add --clear to wipe first)
python data/generate_dummy_data.py --clear

# Quick verify
mysql -h 127.0.0.1 -P 9030 -u root hl_customer_outbound \
  -e "SELECT picklist_source_location_label AS bin,
             COUNT(DISTINCT picklist_item_fsn) AS distinct_fsns,
             COUNT(*) AS total_events
      FROM pendency_mv
      WHERE irt_ticket_id IS NOT NULL
      GROUP BY bin;"
```

Expected output:

| bin | distinct_fsns | total_events |
|-----|---------------|-------------|
| BIN-PHANTOM-A | 5 | 10 |
| BIN-GENUINE-A | 1 | 3 |
| BIN-GENUINE-B | 1 | 3 |
| BIN-GENUINE-C | 1 | 3 |
| BIN-DUAL-A | 4 | 4 |
| BIN-DUAL-B | 1 | 1 |
| BIN-DUAL-C | 1 | 1 |
| BIN-PICKER-A | 4 | 8 |
| BIN-GRN-A | 4 | 4 |
| BIN-NOISE-1 | 1 | 1 |
| BIN-NOISE-2 | 1 | 1 |

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Fixed seed | `random.seed(42)` | Same data every run; demos are deterministic |
| `--clear` is opt-in | Not default | Prevents accidental data loss when re-running |
| S4/S5 SQL verdict = PHANTOM | Intentional | Graph signals are additive; SQL base verdict is always correct |
| `recommendation_log` pre-seeded | 2 verified rows | Feedback UI works on day 1 without full flow run |
| `EXPECTED_VERDICTS` as inline dict | Module-level constant | Zero extra files; importable by a future accuracy-checker script |
