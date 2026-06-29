# LLD 05 · API Contracts

> Status: `GET /diagnoses` **DONE** (M5 · 2026-06-26). `/ask` (M7) and `/feedback` (M8) pending.

---

## `GET /api/diagnoses` ✅

**Query params**

| Param | Type | Default | Validation |
|-------|------|---------|-----------|
| `warehouse_id` | string | null (all warehouses) | — |
| `window_days` | int | 1 | ge=1, le=30 |

**Response** — JSON array, ordered by `orders_impacted DESC`

```json
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
  }
]
```

`graph_signals` is `{}` in M5; filled by M6 with `picker_concentration`, `shared_grn`, `stocktake_done`.

**Error responses**: 422 if `window_days` is out of range (FastAPI automatic validation).

---

## `POST /api/ask` (planned — M7)

- **Body**: `{ "question": string, "warehouse_id": string? }`
- **Response**: `{ "answer": string, "citations": [{ "type": "sql"|"ngql", "query": string, "rows": [...] }] }`
- **Rule**: every factual claim in `answer` must map to a citation entry.

---

## `GET /api/feedback` ✅ (M8)

**Query params**: `warehouse_id` (optional)

**Response** — array ordered by `suggested_at DESC`:
```json
[
  {
    "id": 1, "warehouse_id": "WH-BLR-001", "bin": "BIN-PHANTOM-A", "fsn": "FSN-S1-001",
    "verdict": "PHANTOM_INVENTORY", "action": "stocktake",
    "status": "verified",
    "suggested_at": "2026-06-25T12:00:00", "resolved_at": "2026-06-25T15:00:00",
    "evidence_ref": "SELECT distinct_fsn_count=5 ...",
    "failures_before": 10, "failures_after": 0, "failures_ceased": 10
  }
]
```

`failures_ceased` is `null` when `failures_after` has not been captured yet.

---

## `POST /api/feedback` ✅ (M8)

**Body**:
```json
{ "warehouse_id": "WH-BLR-001", "bin": "BIN-X", "fsn": "FSN-Y",
  "verdict": "PHANTOM_INVENTORY", "evidence_ref": "..." }
```
- `verdict` validated against enum: `PHANTOM_INVENTORY | GENUINE_STOCKOUT | DUAL | AMBIGUOUS`
- `failures_before` captured from live pendency_mv COUNT at POST time.
- Returns the created row (status=`suggested`). HTTP 201.

---

## `PATCH /api/feedback/{id}/status` ✅ (M8)

**Body**: `{ "status": "acknowledged" | "executed" | "verified" }`

- Validates lifecycle order: `suggested→acknowledged→executed→verified`.
  Returns HTTP 400 for invalid transitions (e.g. skipping steps).
- On `executed`: captures `failures_after` from live pendency_mv; computes `failures_ceased`.
- On `verified`: sets `resolved_at` timestamp.
