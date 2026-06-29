# backend/services/diagnosis.py + backend/routers/diagnoses.py — Code Walkthrough

> Source: `backend/services/diagnosis.py`, `backend/routers/diagnoses.py`
> Milestone: M5 · Last updated: 2026-06-26

## What it does

Implements the PS validation SQL verbatim, wraps it in a FastAPI endpoint, and
adds a recovery-projection estimate on top of raw verdict counts.

---

## File structure

```
backend/
├── services/
│   └── diagnosis.py   ← verdict SQL, recovery math, DiagnosisRow dataclass
└── routers/
    └── diagnoses.py   ← GET /api/diagnoses route handler
```

---

## `backend/services/diagnosis.py`

### `DiagnosisRow` dataclass

```python
@dataclass
class DiagnosisRow:
    warehouse_id: str
    bin: str
    fsn: str
    failures: int
    orders_impacted: int
    distinct_fsns: int
    distinct_bins: int
    verdict: str
    recovery_pct: float = 0.0
    graph_signals: dict = field(default_factory=dict)  # filled by M6
```

`graph_signals` is an empty dict in M5 — it will be populated by the M6 graph
enrichment layer without changing the dataclass shape or the API contract.

### The PS verdict SQL (CTE)

```sql
WITH inf AS (
    SELECT wh, bin, fsn,
           COUNT(*) AS failures,
           COUNT(DISTINCT order_id) AS orders
    FROM pendency_mv
    WHERE irt_ticket_id IS NOT NULL
      AND updated_at >= NOW() - INTERVAL %(window_days)s DAY
    GROUP BY 1, 2, 3
),
bin_sum AS (SELECT wh, bin, COUNT(DISTINCT fsn) AS distinct_fsns FROM inf GROUP BY 1,2),
fsn_sum AS (SELECT wh, fsn, COUNT(DISTINCT bin) AS distinct_bins FROM inf GROUP BY 1,2)
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

Thresholds (`phantom_thr`, `stockout_thr`) come from `settings` so they are
adjustable via env vars without code changes (defaults: 3 / 2 from the PS).

### Recovery projection

```python
def _compute_recovery(rows):
    wh_totals = {}          # sum of orders_impacted per warehouse
    for r in rows:
        wh_totals[r["warehouse_id"]] += r["orders_impacted"]

    for r in rows:
        pct = r["orders_impacted"] / wh_totals[r["warehouse_id"]] * 100
```

`recovery_pct` is the fraction of all impacted orders in the warehouse that
this specific (bin, fsn) cluster is responsible for. Fixing it recovers that
percentage of fill-rate. Ranked highest → most impactful fix.

### `get_diagnoses()`

```python
def get_diagnoses(warehouse_id=None, window_days=None) -> list[DiagnosisRow]:
    ...
    conn = get_connection()
    cur.execute(_VERDICT_SQL, params)
    raw_rows = cur.fetchall()
    ...
    if warehouse_id:
        raw_rows = [r for r in raw_rows if r["warehouse_id"] == warehouse_id]
    recovery_map = _compute_recovery(raw_rows)
    return [DiagnosisRow(..., recovery_pct=recovery_map[key]) for r in raw_rows]
```

Warehouse filter is applied in Python (not SQL) so the CTE runs once and
recovery_pct denominators are computed over the full warehouse population.

---

## `backend/routers/diagnoses.py`

```python
@router.get("/diagnoses")
def diagnoses_endpoint(
    warehouse_id: str | None = Query(...),
    window_days: int = Query(default=1, ge=1, le=30),
):
    rows = get_diagnoses(warehouse_id=warehouse_id, window_days=window_days)
    return [asdict(r) for r in rows]
```

- `ge=1, le=30` validates window_days — FastAPI returns 422 automatically for invalid values.
- `asdict(r)` converts the dataclass to a JSON-serialisable dict. `graph_signals` is an
  empty dict in M5 — the field exists in the response contract already so M6 can fill it
  without breaking the frontend.

---

## API contract

```
GET /api/diagnoses?warehouse_id=WH-BLR-001&window_days=1

Response (array):
[
  {
    "warehouse_id": "WH-BLR-001",
    "bin": "BIN-PHANTOM-A",
    "fsn": "FSN-S1-001",
    "failures": 2,
    "orders_impacted": 2,
    "distinct_fsns": 5,
    "distinct_bins": 1,
    "verdict": "PHANTOM_INVENTORY",
    "recovery_pct": 5.3,
    "graph_signals": {}
  },
  ...
]
```

---

## Technical decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| PS SQL verbatim | Match exactly | Re-write with ORM | PS is the spec; any deviation changes verdict semantics |
| Warehouse filter in Python | Post-SQL filter | WHERE clause in SQL | Recovery_pct denominator must include all wh rows; SQL filter would skew it |
| `window_days` param | Query param (default 1) | Hardcoded | Thresholds + window configurable without redeploy |
| `graph_signals: dict = {}` | Empty field in M5 | Add in M6 | API shape stable now; M6 fills it without breaking contracts |
| `dataclasses.asdict` | For JSON serialisation | Pydantic model | Simpler for internal service; Pydantic would add schema docs — acceptable future upgrade |
