# LLD 04 · Graph Signal Queries

> Status: **DONE** (M6 · 2026-06-26). Source: `backend/services/graph.py`.

---

## Design principle

All signals are **additive** — if NebulaGraph is unavailable or a query fails,
that signal returns `{}` and the SQL verdict stands. No signal can block the API.

Signals are computed **once per unique (wh, bin)**, not once per (wh, bin, fsn) row,
to minimise graph round-trips on the response path.

---

## Signal 1 — `picker_concentration` (picker overlap)

**Hypothesis**: if 100% of ASSIGNED_TO edges on a BIN come from one picker, the INFs
are likely due to picker error, not phantom inventory.

**nGQL**:
```ngql
MATCH (p:Picker)-[:ASSIGNED_TO]->(b:BIN)
WHERE id(b) == "WH-BLR-001:BIN-PICKER-A"
RETURN p.Picker.picker_id AS picker_id
```

**Logic**: count picker_id occurrences; `concentration = dominant_count / total`.
If `concentration >= 0.7` → return `{"picker_concentration": float, "dominant_picker": str}`.

**Threshold**: 0.7 (70%) — hardcoded in `graph.py` constant `PICKER_CONCENTRATION_THRESHOLD`.

---

## Signal 2 — `shared_grn` (shared inbound batch)

**Hypothesis**: if all FSNs failing in a BIN were received in the same GRN batch,
the root cause is likely a bad inbound shipment.

**nGQL** (two-hop):
```ngql
MATCH (f:FSN)-[:FAILED_AT]->(b:BIN), (f)-[:RECEIVED_IN]->(g:GRN)
WHERE id(b) == "WH-BLR-001:BIN-GRN-A"
RETURN f.FSN.fsn AS fsn, g.GRN.grn_id AS grn_id
```

**Logic**: collect all `grn_id` values; if exactly 1 unique GRN → return `{"shared_grn": grn_id, "fsn_count": int}`.

---

## Signal 3 — `stocktake_done` (closed-loop feedback)

**Hypothesis**: if a STOCKTAKE edge already exists on this BIN, a stocktake has
already been triggered — useful for the Feedback UI to show loop status.

**nGQL**:
```ngql
MATCH (b:BIN)-[s:STOCKTAKE]->(v:Variance)
WHERE id(b) == "WH-BLR-001:BIN-PHANTOM-A"
RETURN s.STOCKTAKE.done_at AS done_at LIMIT 1
```

**Logic**: if `row_size() > 0` → return `{"stocktake_done": True}`.

---

## Signal 4 — `atp_likely_zero` (ATP proxy stub)

**Hypothesis**: if `distinct_bins >= STOCKOUT_THRESHOLD`, the item is failing in
multiple locations and is likely genuinely depleted (ATP ≈ 0).

**Implementation**: conservative proxy — no external service call in this milestone.
Production path: query inventory/ATP service REST endpoint.

**Logic**: `if distinct_bins >= settings.stockout_bin_threshold → {"atp_likely_zero": True}`.

---

## Enrichment wiring in `diagnosis.py`

```python
# Deduplicate: enrich once per (wh, bin), not once per (wh, bin, fsn) row
seen_bins = set()
bin_signals = {}
for r in raw_rows:
    key = (r["warehouse_id"], r["bin"])
    if key not in seen_bins:
        seen_bins.add(key)
        bin_signals[key] = enrich_signals(wh=r["warehouse_id"],
                                          bin_label=r["bin"],
                                          distinct_bins=r["distinct_bins"])
```

---

## Key Technical Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| All signals additive | Return `{}` on failure | Raise exception | Graph enrichment must never block SQL verdict |
| Enrich once per (wh, bin) | Deduplicate before loop | Once per (wh,bin,fsn) | N FSNs per BIN → N graph calls reduced to 1 |
| Picker threshold 0.7 | Module constant | Env var / settings | Simple for demo; clearly annotated for production |
| ATP as stub | `distinct_bins` proxy | Real ATP service call | No ATP service in scope; stub is labelled and documented |
| Per-signal try/except in `enrich_signals` | Individual try/except | Single outer try | One failing signal must not suppress the others |
