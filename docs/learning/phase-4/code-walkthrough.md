# Phase 4 Code Walkthrough

Phase 4 files:

1. `backend/routers/diagnoses.py`
2. `backend/services/diagnosis.py`
3. `frontend/src/api.js`
4. `frontend/src/DiagnosesTable.jsx`
5. `docs/code-walkthroughs/backend-diagnoses.md`

This phase explains the deterministic diagnoses API from frontend call to SQL
result to rendered table.

## File 1: `backend/routers/diagnoses.py`

### Purpose

This file defines the HTTP endpoint:

```text
GET /api/diagnoses
```

Remember: `backend/main.py` mounts this router with:

```python
prefix="/api"
```

So the router path:

```text
/diagnoses
```

becomes:

```text
/api/diagnoses
```

### Imports

```python
from dataclasses import asdict
from fastapi import APIRouter, Query
from backend.services.diagnosis import get_diagnoses
```

Meaning:

```text
asdict -> convert dataclass objects into dictionaries
APIRouter -> create a FastAPI router
Query -> define/validate query parameters
get_diagnoses -> business logic service function
```

### Router Object

```python
router = APIRouter()
```

This creates the router that `main.py` later includes.

### Endpoint

```python
@router.get("/diagnoses")
def diagnoses_endpoint(...):
```

This means:

```text
When a GET request hits /api/diagnoses, run diagnoses_endpoint().
```

### Query Parameters

```python
warehouse_id: str | None = Query(default=None, description="Filter to one warehouse")
window_days: int = Query(default=1, ge=1, le=30, description="Lookback window in days")
```

Meaning:

```text
warehouse_id is optional.
window_days defaults to 1.
window_days must be between 1 and 30.
```

If a caller sends:

```text
/api/diagnoses?window_days=0
```

FastAPI rejects it with validation error because `ge=1`.

### Calling The Service

```python
rows = get_diagnoses(warehouse_id=warehouse_id, window_days=window_days)
```

The router does not compute verdicts itself.

It delegates to:

```text
backend/services/diagnosis.py
```

### Returning JSON

```python
return [asdict(r) for r in rows]
```

`get_diagnoses()` returns dataclass objects.

`asdict()` converts each object into a normal dictionary so FastAPI can serialize
it as JSON.

## File 2: `backend/services/diagnosis.py`

### Purpose

This is the deterministic verdict engine.

It:

```text
runs SQL against StarRocks
computes PHANTOM / GENUINE / DUAL / AMBIGUOUS
computes recovery_pct
returns DiagnosisRow objects
```

### Imports

```python
import logging
from dataclasses import dataclass, field
from backend.config import settings
from backend.db.starrocks import get_connection
```

Important:

```text
settings -> thresholds and defaults
get_connection -> StarRocks connection
dataclass -> structured output row
logging -> records backend messages/errors
```

Note:

```text
field is imported but not used in the current implementation.
```

This is likely leftover from an older version where `graph_signals` was included
in the dataclass.

### `DiagnosisRow`

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
```

This is the backend output shape.

Meaning:

| Field | Meaning |
|---|---|
| `warehouse_id` | Warehouse/dark store. |
| `bin` | Physical BIN/location. |
| `fsn` | Product/item. |
| `failures` | Number of failure rows for this warehouse/BIN/FSN. |
| `orders_impacted` | Distinct orders affected. |
| `distinct_fsns` | How many different FSNs failed in this BIN. |
| `distinct_bins` | How many different BINs this FSN failed across. |
| `verdict` | Root-cause category. |
| `recovery_pct` | Relative impact estimate. |

### Important Docs/Code Drift

The older walkthrough `docs/code-walkthroughs/backend-diagnoses.md` says
`DiagnosisRow` has:

```text
graph_signals
```

But the current actual dataclass in `backend/services/diagnosis.py` does **not**
include `graph_signals`.

The frontend handles missing graph signals safely because it calls:

```javascript
<GraphSignals signals={r.graph_signals} />
```

and `GraphSignals` returns a dash if `signals` is missing or empty.

Still, this is a real documentation/API drift to remember:

```text
docs mention graph_signals in /diagnoses
current response likely omits graph_signals
frontend tolerates that
```

### `_VERDICT_SQL`

This is the core SQL query.

It has four parts:

```text
inf
bin_sum
fsn_sum
final SELECT with CASE
```

#### `inf`

```sql
WITH inf AS (
    SELECT
        reservation_warehouse_id AS wh,
        picklist_source_location_label AS bin,
        picklist_item_fsn AS fsn,
        COUNT(*) AS failures,
        COUNT(DISTINCT order_id) AS orders
    FROM pendency_mv
    WHERE irt_ticket_id IS NOT NULL
      AND updated_at >= NOW() - INTERVAL %(window_days)s DAY
    GROUP BY 1, 2, 3
)
```

Beginner translation:

```text
Take recent rows from pendency_mv.
Keep only rows with IRT ticket IDs.
Group them by warehouse, BIN, and FSN.
Count failures and distinct orders.
```

#### `bin_sum`

```sql
SELECT wh, bin, COUNT(DISTINCT fsn) AS distinct_fsns
```

Meaning:

```text
For each warehouse + BIN, count how many different FSNs failed.
```

This powers:

```text
PHANTOM_INVENTORY
```

#### `fsn_sum`

```sql
SELECT wh, fsn, COUNT(DISTINCT bin) AS distinct_bins
```

Meaning:

```text
For each warehouse + FSN, count how many different BINs it failed across.
```

This powers:

```text
GENUINE_STOCKOUT
```

#### `CASE`

```sql
CASE
    WHEN b.distinct_fsns >= %(phantom_thr)s AND f.distinct_bins >= %(stockout_thr)s
        THEN 'DUAL'
    WHEN b.distinct_fsns >= %(phantom_thr)s
        THEN 'PHANTOM_INVENTORY'
    WHEN f.distinct_bins >= %(stockout_thr)s
        THEN 'GENUINE_STOCKOUT'
    ELSE 'AMBIGUOUS'
END AS verdict
```

This is the Phase 1 verdict rule implemented in SQL.

### `_compute_recovery(rows)`

This function computes:

```text
recovery_pct = orders_impacted_for_row / total_orders_impacted_for_warehouse * 100
```

Example:

```text
warehouse total impacted orders = 100
this row impacted orders = 20
recovery_pct = 20%
```

This does not decide the verdict.

It helps rank impact.

### `get_diagnoses(...)`

This is the public service function.

Flow:

```text
choose window_days
prepare SQL params
open StarRocks connection
execute _VERDICT_SQL
fetch rows
close connection
optionally filter by warehouse_id
compute recovery_pct
build DiagnosisRow objects
return list
```

Important exception behavior:

```python
except Exception:
    logger.exception("Failed to run verdict SQL")
    return []
```

Meaning:

```text
If SQL/database fails, return an empty list instead of raising an API error.
```

This is demo-friendly, but in production you might want a clearer error response.

## File 3: `frontend/src/api.js`

### Purpose

This file centralizes frontend API calls.

It creates:

```javascript
const http = axios.create({ baseURL: '/api' })
```

Meaning:

```text
All requests are relative to /api.
```

### `fetchDiagnoses`

```javascript
export const fetchDiagnoses = (warehouseId, windowDays = 1) =>
  http.get('/diagnoses', {
    params: {
      ...(warehouseId && { warehouse_id: warehouseId }),
      window_days: windowDays,
    },
  }).then(r => r.data)
```

Meaning:

```text
Call GET /api/diagnoses.
Send warehouse_id only if it exists.
Always send window_days.
Return response data.
```

If:

```javascript
fetchDiagnoses("WH-BLR-001", 3)
```

then request becomes:

```text
GET /api/diagnoses?warehouse_id=WH-BLR-001&window_days=3
```

## File 4: `frontend/src/DiagnosesTable.jsx`

### Purpose

This component renders the diagnosis table.

It:

```text
loads diagnosis rows
shows loading/error/empty states
renders verdict badges
renders counts and recovery percentage
lets user log a recommendation
```

### Verdict Labels

```javascript
const VERDICT_LABELS = {
  PHANTOM_INVENTORY: { label: 'Phantom Inventory', cls: 'badge-phantom' },
  GENUINE_STOCKOUT:  { label: 'Genuine Stockout',  cls: 'badge-genuine' },
  DUAL:              { label: 'Dual',               cls: 'badge-dual' },
  AMBIGUOUS:         { label: 'Ambiguous',          cls: 'badge-ambiguous' },
}
```

This maps backend verdict codes to user-friendly labels and CSS classes.

### `VerdictBadge`

```javascript
function VerdictBadge({ verdict }) { ... }
```

This renders the colored verdict badge.

### `GraphSignals`

```javascript
function GraphSignals({ signals }) { ... }
```

This displays graph signals if present.

Important:

```javascript
if (!signals || Object.keys(signals).length === 0) return <span className="muted">—</span>
```

So missing `graph_signals` does not crash the UI.

### State

```javascript
const [rows, setRows] = useState([])
const [loading, setLoading] = useState(false)
const [error, setError] = useState(null)
const [window, setWindow] = useState(1)
const [logging, setLogging] = useState({})
```

Meaning:

| State | Meaning |
|---|---|
| `rows` | Diagnosis rows from backend. |
| `loading` | Whether table is currently loading. |
| `error` | API error message. |
| `window` | Selected lookback window in days. |
| `logging` | Tracks which row is currently logging a recommendation. |

### `load()`

```javascript
const load = () => {
  setLoading(true)
  setError(null)
  fetchDiagnoses(warehouseId, window)
    .then(setRows)
    .catch(e => setError(e.message))
    .finally(() => setLoading(false))
}
```

Meaning:

```text
Set loading state.
Clear old error.
Call backend.
Store returned rows.
Store error if failed.
Stop loading.
```

### `useEffect`

```javascript
useEffect(() => { load() }, [warehouseId, window])
```

Meaning:

```text
Whenever warehouseId or window changes, reload diagnoses.
```

### `logRec(row)`

This sends a recommendation to the feedback API.

It uses the row data:

```javascript
warehouse_id: row.warehouse_id
bin: row.bin
fsn: row.fsn
verdict: row.verdict
evidence_ref: `distinct_fsns=${row.distinct_fsns}, distinct_bins=${row.distinct_bins}`
```

So the diagnosis table is connected to the feedback loop.

### Table Render

The table columns are:

```text
BIN
FSN
Verdict
Failures
Orders Impacted
Distinct FSNs
Distinct BINs
Recovery %
Graph Signals
Action
```

These directly correspond to backend diagnosis fields.

## File 5: `docs/code-walkthroughs/backend-diagnoses.md`

This file is an existing walkthrough.

It explains the same endpoint and SQL, but it appears slightly outdated:

```text
It says DiagnosisRow includes graph_signals.
Current actual code does not include that field.
```

Use it as a helpful guide, but trust the actual code when they differ.

## End-To-End Phase 4 Flow

```text
DiagnosesTable.jsx mounts
  -> useEffect calls load()
  -> load() calls fetchDiagnoses(warehouseId, window)
  -> api.js sends GET /api/diagnoses
  -> FastAPI routes request to diagnoses_endpoint()
  -> diagnoses_endpoint() calls get_diagnoses()
  -> get_diagnoses() runs _VERDICT_SQL in StarRocks
  -> SQL computes failures, orders, distinct_fsns, distinct_bins, verdict
  -> Python computes recovery_pct
  -> DiagnosisRow objects return to router
  -> router converts dataclasses to dicts
  -> FastAPI returns JSON
  -> frontend stores rows in state
  -> table renders verdicts and counts
```

## Concrete Example

Seeded data has:

```text
BIN-PHANTOM-A with 5 distinct FSNs
```

SQL computes:

```text
distinct_fsns = 5
distinct_bins = 1
```

Verdict:

```text
PHANTOM_INVENTORY
```

Frontend displays:

```text
BIN-PHANTOM-A
FSN-S1-001
Phantom Inventory badge
distinct FSNs = 5
distinct BINs = 1
```

## Phase 4 Takeaways

1. `/api/diagnoses` is a read-only GET endpoint.
2. The router delegates verdict work to `services/diagnosis.py`.
3. `_VERDICT_SQL` implements the deterministic Phase 1 rules.
4. `recovery_pct` ranks impact but does not decide verdict.
5. The frontend fetches rows through `api.js` and renders them in `DiagnosesTable.jsx`.
6. There is docs/code drift around `graph_signals`.
