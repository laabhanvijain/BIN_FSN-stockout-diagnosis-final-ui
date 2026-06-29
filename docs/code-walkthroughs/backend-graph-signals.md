# backend/services/graph.py — Code Walkthrough

> Source: `backend/services/graph.py` (+ wiring in `backend/services/diagnosis.py`)
> Milestone: M6 · Last updated: 2026-06-26

## What it does

Runs 4 nGQL graph queries for each unique (wh, bin) pair in a diagnosis batch
and merges results into the `graph_signals` field of each `DiagnosisRow`. All
signals are additive — any failure returns `{}` and the SQL verdict is unaffected.

---

## File structure

```
backend/services/graph.py
├── PICKER_CONCENTRATION_THRESHOLD = 0.7
├── _exec(session, ngql)            — execute + log nGQL
├── _bin_vid(wh, label)             — "wh:label" VID helper
├── get_picker_concentration(wh, bin) → dict
├── get_shared_grn(wh, bin)          → dict
├── get_stocktake_done(wh, bin)      → dict
├── get_atp_proxy(distinct_bins)     → dict
└── enrich_signals(wh, bin, distinct_bins) → merged dict
```

---

## Signal walkthroughs

### 1. `get_picker_concentration(wh, bin_label)`

```python
ngql = """
MATCH (p:Picker)-[:ASSIGNED_TO]->(b:BIN)
WHERE id(b) == "{wh}:{bin}"
RETURN p.Picker.picker_id AS picker_id
"""
picker_ids = [row[0] for row in result]
counts = Counter(picker_ids)
concentration = dominant_count / total
if concentration >= 0.7:
    return {"picker_concentration": concentration, "dominant_picker": dominant_picker}
```

Walks the reversed `ASSIGNED_TO` edge (Picker → BIN). Counts how many picks
came from each picker. If one picker accounts for ≥ 70%, it's a picker-error signal.

For `BIN-PICKER-A` in the demo: all 8 picks are from `PKR-BAD` → `concentration = 1.0`.

### 2. `get_shared_grn(wh, bin_label)`

```python
ngql = """
MATCH (f:FSN)-[:FAILED_AT]->(b:BIN), (f)-[:RECEIVED_IN]->(g:GRN)
WHERE id(b) == "{wh}:{bin}"
RETURN f.FSN.fsn AS fsn, g.GRN.grn_id AS grn_id
"""
grn_ids = set(row["grn_id"] for row in result)
if len(grn_ids) == 1:
    return {"shared_grn": grn_ids.pop(), "fsn_count": fsn_count}
```

Two-hop pattern: FSN → BIN (FAILED_AT) **and** FSN → GRN (RECEIVED_IN).
If all failing FSNs in the BIN came from a single GRN, return it.

For `BIN-GRN-A` in the demo: 4 FSNs, all `grn_id = GRN-SHARED-999` → signal fires.

### 3. `get_stocktake_done(wh, bin_label)`

```python
ngql = """
MATCH (b:BIN)-[s:STOCKTAKE]->(v:Variance)
WHERE id(b) == "{wh}:{bin}"
RETURN s.STOCKTAKE.done_at LIMIT 1
"""
if result.row_size() > 0:
    return {"stocktake_done": True}
```

Single-hop: BIN → Variance via STOCKTAKE edge. If the edge exists,
a stocktake was already done. Useful for the Feedback UI (loop closed).

### 4. `get_atp_proxy(distinct_bins)`

```python
if distinct_bins >= settings.stockout_bin_threshold:
    return {"atp_likely_zero": True}
```

Not a graph query — a conservative proxy. Real implementation:
call inventory/ATP service. Clearly annotated as a stub.

---

## `enrich_signals()` — the public entry point

```python
def enrich_signals(wh, bin_label, distinct_bins) -> dict:
    signals = {}
    try: signals.update(get_picker_concentration(...))
    except Exception: logger.exception(...)

    try: signals.update(get_shared_grn(...))
    except Exception: logger.exception(...)

    try: signals.update(get_stocktake_done(...))
    except Exception: logger.exception(...)

    try: signals.update(get_atp_proxy(...))
    except Exception: logger.exception(...)

    return signals
```

Each signal has its own `try/except` — one failure never suppresses the others.

---

## Wiring into `diagnosis.py`

```python
# Deduplicate: enrich once per (wh, bin), not per (wh, bin, fsn)
seen_bins = set()
bin_signals = {}
for r in raw_rows:
    key = (r["warehouse_id"], r["bin"])
    if key not in seen_bins:
        seen_bins.add(key)
        bin_signals[key] = enrich_signals(
            wh=r["warehouse_id"],
            bin_label=r["bin"],
            distinct_bins=r["distinct_bins"],
        )
```

If a BIN has 5 FSNs, the graph is queried once, not 5 times.
All 5 `DiagnosisRow` objects for that BIN get the same `graph_signals` dict.

---

## Expected output for seeded data

| BIN | `graph_signals` |
|-----|----------------|
| BIN-PHANTOM-A | `{}` (no picker concentration, no shared GRN) |
| BIN-GENUINE-A/B/C | `{"atp_likely_zero": true}` |
| BIN-DUAL-A | `{"atp_likely_zero": true}` (FSN-S3-001 crosses bins) |
| BIN-PICKER-A | `{"picker_concentration": 1.0, "dominant_picker": "PKR-BAD"}` |
| BIN-GRN-A | `{"shared_grn": "GRN-SHARED-999", "fsn_count": 4}` |
| BIN-NOISE-1/2 | `{}` |

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Additive signals | `{}` on failure | Graph must never block SQL verdict |
| Enrich per (wh, bin) | Deduplicate first | Avoids N graph calls for N FSNs in one BIN |
| Per-signal try/except | Individual wrapping | One bad signal doesn't suppress the rest |
| Picker threshold = 0.7 | Module constant | Simple for demo; easy to move to settings |
| ATP = stub | `distinct_bins` proxy | No ATP service in scope; labelled for production |
| MATCH pattern for two-hop | Comma-separated patterns | Standard nGQL multi-hop; readable and correct |
