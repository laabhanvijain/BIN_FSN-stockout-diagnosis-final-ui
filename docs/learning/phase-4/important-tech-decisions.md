# Phase 4 Important Technical Decisions

This file captures important decisions in the diagnoses API.

## Decision 1: Keep The Router Thin

### Choice

`backend/routers/diagnoses.py` only:

```text
accepts query parameters
calls get_diagnoses()
converts dataclasses to dicts
returns JSON
```

### Why

The router should stay focused on HTTP concerns.

Business logic belongs in:

```text
backend/services/diagnosis.py
```

### Trade-Off

For a very tiny app, putting logic in the router might be quicker. But the
service split is cleaner and scales better.

## Decision 2: Use PS Verdict SQL Directly

### Choice

Use a raw SQL query matching the problem-statement verdict logic.

### Why

The SQL is the spec for the deterministic verdict.

Using it directly avoids accidentally changing semantics through an ORM or
rewritten logic.

### Trade-Off

Raw SQL is less abstract than ORM code, but here that is a benefit because the
business rule is SQL-shaped.

## Decision 3: Query Parameters For Warehouse And Time Window

### Choice

Expose:

```text
warehouse_id
window_days
```

as query parameters.

### Why

The frontend can reload diagnoses for:

```text
one warehouse
different lookback windows
```

without changing backend code.

### Trade-Off

The backend must validate these inputs. FastAPI handles `window_days` validation
with:

```python
ge=1, le=30
```

## Decision 4: Use Dataclass For Internal Diagnosis Rows

### Choice

Use:

```python
@dataclass
class DiagnosisRow
```

### Why

It is simple and lightweight.

The service can return structured Python objects, and the router can serialize
them with:

```python
asdict()
```

### Trade-Off

Pydantic response models would provide stronger API docs and validation. This
would be a reasonable future improvement.

## Decision 5: Compute `recovery_pct` In Python

### Choice

Run the verdict SQL first, then compute recovery percentage in Python.

### Why

The verdict is pure SQL. Recovery projection is a post-processing/ranking
calculation.

Keeping it separate makes the SQL easier to understand.

### Trade-Off

For very large result sets, computing in Python may be less efficient than doing
more in SQL.

## Decision 6: Return Empty List On SQL Failure

### Choice

If the verdict SQL fails:

```python
logger.exception(...)
return []
```

### Why

This keeps the demo UI from crashing.

### Trade-Off

For production, returning an empty list can hide real failures. A clearer HTTP
error might be better.

## Decision 7: Frontend Centralizes API Calls In `api.js`

### Choice

Use:

```text
frontend/src/api.js
```

as the single place for frontend HTTP functions.

### Why

Components do not need to know Axios details. They call named functions like:

```javascript
fetchDiagnoses(...)
```

### Trade-Off

For a small app this is simple. Larger apps may use React Query, SWR, or a typed
API client.

## Decision 8: Diagnosis Table Can Log Recommendations

### Choice

`DiagnosesTable.jsx` includes a `Log Rec` button.

### Why

It connects diagnosis output directly to the feedback loop.

The table is not only informational; it lets users start action tracking.

### Trade-Off

This couples the diagnosis table to feedback creation. It is acceptable for the
demo, but larger apps might separate the action into a modal or workflow service.

## Decision 9: Graph Signals Are Tolerated As Missing

### Choice

The frontend renders a dash when graph signals are missing:

```javascript
if (!signals || Object.keys(signals).length === 0) return <span className="muted">—</span>
```

### Why

The diagnoses table can work even if graph enrichment is absent.

### Trade-Off

There is docs/code drift: older docs say `graph_signals` exists in
`DiagnosisRow`, but current actual code omits it. The UI tolerates this, but the
API contract should eventually be clarified.
