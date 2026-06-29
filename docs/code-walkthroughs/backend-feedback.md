# backend/services/feedback.py + backend/routers/feedback.py — Code Walkthrough

> Source: `backend/services/feedback.py`, `backend/routers/feedback.py`
> Milestone: M8 · Last updated: 2026-06-26

## What it does

Implements the closed-loop feedback system: every diagnosis can generate a
recommendation, ops advances it through a lifecycle, and the system measures
whether the action actually reduced INF failures.

---

## File structure

```
backend/
├── services/
│   └── feedback.py   ← CRUD, lifecycle transitions, failures_ceased computation
└── routers/
    └── feedback.py   ← GET /api/feedback, POST /api/feedback, PATCH .../status
```

---

## The lifecycle

```
suggested  →  acknowledged  →  executed  →  verified
    │                              │              │
    │ failures_before captured     │ failures_after  │ resolved_at set
    │ at POST time (live COUNT)    │ captured here   │
```

The key insight: `failures_before` is a **snapshot at suggestion time**, not
a retrospective calculation. This locks in the pre-action baseline even if
more failures arrive before the action is taken.

---

## `backend/services/feedback.py`

### `_live_failures(conn, wh, bin, fsn)`

```python
sql = """
    SELECT COUNT(*) AS cnt FROM pendency_mv
    WHERE reservation_warehouse_id = %(wh)s
      AND picklist_source_location_label = %(bin)s
      AND picklist_item_fsn = %(fsn)s
      AND irt_ticket_id IS NOT NULL
"""
```

Counts current open INF events for a triple. Called at POST (for `failures_before`)
and at PATCH status=`executed` (for `failures_after`).

### `list_recommendations()`

```python
for r in rows:
    if r["failures_before"] is not None and r["failures_after"] is not None:
        r["failures_ceased"] = r["failures_before"] - r["failures_after"]
    else:
        r["failures_ceased"] = None
```

`failures_ceased` is computed in Python rather than SQL. Positive = loop closed;
0 = action had no effect; negative = situation worsened (useful for alerting).

### `create_recommendation()`

```python
failures_before = _live_failures(conn, warehouse_id, bin_label, fsn)
INSERT INTO recommendation_log (..., status='suggested', failures_before=N)
```

Action is derived from verdict via `VERDICT_TO_ACTION`:
- `PHANTOM_INVENTORY` → `stocktake`
- `GENUINE_STOCKOUT` → `replenish`
- `DUAL` → `stocktake + replenish`
- `AMBIGUOUS` → `investigate`

### `advance_status()`

```python
VALID_TRANSITIONS = {
    "suggested": "acknowledged",
    "acknowledged": "executed",
    "executed": "verified",
}

if new_status != expected_next:
    raise ValueError(f"Invalid transition: {current} → {new_status}")
```

Each step is validated against the dict — no skipping allowed. On `executed`:
```python
failures_after = _live_failures(conn, wh, bin, fsn)
UPDATE recommendation_log SET failures_after = N, status = 'executed' WHERE id = ?
```

On `verified`:
```python
UPDATE recommendation_log SET resolved_at = NOW(), status = 'verified' WHERE id = ?
```

---

## `backend/routers/feedback.py`

```python
class CreateRecommendationRequest(BaseModel):
    verdict: str = Field(..., pattern=r"^(PHANTOM_INVENTORY|GENUINE_STOCKOUT|DUAL|AMBIGUOUS)$")

class AdvanceStatusRequest(BaseModel):
    status: str = Field(..., pattern=r"^(acknowledged|executed|verified)$")
```

Pydantic regex patterns validate both the verdict enum and the allowed target
statuses. `suggested` is excluded from `AdvanceStatusRequest` because you can
never transition *to* `suggested` — it is the initial state only.

---

## Example closed loop (seeded data)

```
GET /api/feedback
→ [{ id: 1, bin: "BIN-PHANTOM-A", failures_before: 10, failures_after: 0,
     failures_ceased: 10, status: "verified" }]
```

The seeded row shows `failures_ceased = 10` — all 10 INF events stopped after
the stocktake was done. This is the closed-loop confirmation shown in the UI.

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| `failures_before` at POST time | Live COUNT snapshot | Baseline locked at suggestion; immune to subsequent arrivals |
| `failures_after` at `executed` | Live COUNT at PATCH | Measures actual post-action state; not stale data |
| Lifecycle validated server-side | `VALID_TRANSITIONS` dict | Prevents skipping steps; enforces operational discipline |
| Action derived from verdict | `VERDICT_TO_ACTION` dict | Single source of truth; consistent across create paths |
| `failures_ceased` in Python | Post-query arithmetic | Keeps SQL generic; StarRocks DUPLICATE KEY makes complex UPDATE-SELECT fragile |
| `suggested` excluded from target status | Pydantic pattern | You can never transition back to `suggested` |
