# LLD 03 · Verdict Algorithm

> Status: **DONE** (M5 · 2026-06-26). Source: `backend/services/diagnosis.py`, `backend/routers/diagnoses.py`.

---

## SQL (PS verbatim)

```sql
WITH inf AS (
    SELECT reservation_warehouse_id AS wh,
           picklist_source_location_label AS bin,
           picklist_item_fsn AS fsn,
           COUNT(*) AS failures,
           COUNT(DISTINCT order_id) AS orders
    FROM pendency_mv
    WHERE irt_ticket_id IS NOT NULL
      AND updated_at >= NOW() - INTERVAL %(window_days)s DAY
    GROUP BY 1, 2, 3
),
bin_sum AS (SELECT wh, bin, COUNT(DISTINCT fsn) AS distinct_fsns FROM inf GROUP BY 1, 2),
fsn_sum AS (SELECT wh, fsn, COUNT(DISTINCT bin) AS distinct_bins FROM inf GROUP BY 1, 2)
SELECT i.*, b.distinct_fsns, f.distinct_bins,
    CASE
        WHEN b.distinct_fsns >= %(phantom_thr)s AND f.distinct_bins >= %(stockout_thr)s THEN 'DUAL'
        WHEN b.distinct_fsns >= %(phantom_thr)s                                         THEN 'PHANTOM_INVENTORY'
        WHEN f.distinct_bins >= %(stockout_thr)s                                        THEN 'GENUINE_STOCKOUT'
        ELSE 'AMBIGUOUS'
    END AS verdict
FROM inf i
JOIN bin_sum b ON b.wh = i.wh AND b.bin = i.bin
JOIN fsn_sum f ON f.wh = i.wh AND f.fsn = i.fsn
ORDER BY i.orders DESC, i.failures DESC
```

**Parameters** (all from `settings`, overridable via env vars):

| Param | Default | Env var |
|-------|---------|---------|
| `window_days` | 1 | `DIAGNOSIS_WINDOW_DAYS` |
| `phantom_thr` | 3 | `PHANTOM_FSN_THRESHOLD` |
| `stockout_thr` | 2 | `STOCKOUT_BIN_THRESHOLD` |

---

## Recovery projection formula

```
recovery_pct(bin, fsn) = orders_impacted(bin, fsn) / Σ orders_impacted(wh) × 100
```

Denominator is summed across all (bin, fsn) clusters in the same warehouse within
the window — a conservative lower bound that ranks clusters by relative impact.

Warehouse filter is applied **after** the SQL runs so the denominator always
includes the full warehouse population (not a filtered subset).

---

## DiagnosisRow dataclass

| Field | Type | Populated by |
|-------|------|-------------|
| `warehouse_id`, `bin`, `fsn` | str | SQL |
| `failures`, `orders_impacted` | int | SQL |
| `distinct_fsns`, `distinct_bins` | int | SQL |
| `verdict` | str | SQL CASE |
| `recovery_pct` | float | Python post-processing |
| `graph_signals` | dict | M6 graph service (empty in M5) |

---

## API endpoint

```
GET /api/diagnoses
  ?warehouse_id=WH-BLR-001   (optional)
  &window_days=1              (1–30, default 1)
```

Response: JSON array of `DiagnosisRow` dicts, ordered by `orders_impacted DESC`.

---

## Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| PS SQL verbatim | No deviation | PS is the spec; changes alter verdict semantics |
| Warehouse filter post-SQL | Python filter | Recovery_pct denominator must use full-wh population |
| `graph_signals` field in M5 | Empty dict `{}` | API shape is stable; M6 fills without breaking contracts |
| Thresholds via settings | Env vars | Adjustable without redeploy |
| `dataclasses.asdict` | Not Pydantic | Simpler at this scale; Pydantic is a future upgrade path |
