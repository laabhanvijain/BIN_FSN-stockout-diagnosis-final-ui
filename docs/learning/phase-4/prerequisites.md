# Phase 4 Prerequisites

Phase 4 is about the diagnoses API. Before reading the code, understand these
ideas:

1. HTTP GET request
2. Query parameter
3. JSON response
4. Router
5. Service
6. Dataclass
7. SQL aggregation
8. Frontend data fetching
9. React state

## 1. HTTP GET Request

A GET request asks the backend to return data.

Example:

```text
GET /api/diagnoses
```

Meaning:

```text
Backend, give me diagnosis rows.
```

GET requests should usually read data, not modify data.

## 2. Query Parameter

A query parameter is extra input in the URL.

Example:

```text
/api/diagnoses?warehouse_id=WH-BLR-001&window_days=1
```

Here:

```text
warehouse_id = WH-BLR-001
window_days = 1
```

These let the caller filter or configure the request.

## 3. JSON Response

The backend returns JSON so the frontend can render it.

Example:

```json
{
  "warehouse_id": "WH-BLR-001",
  "bin": "BIN-PHANTOM-A",
  "fsn": "FSN-S1-001",
  "verdict": "PHANTOM_INVENTORY"
}
```

## 4. Router

A router receives an HTTP request and sends it to the correct function.

In Phase 4:

```text
backend/routers/diagnoses.py
```

receives:

```text
GET /api/diagnoses
```

## 5. Service

A service contains business logic.

In Phase 4:

```text
backend/services/diagnosis.py
```

does the actual work:

```text
connect to StarRocks
run verdict SQL
compute recovery percentage
return diagnosis rows
```

## 6. Dataclass

A dataclass is a Python class designed to hold structured data.

In this phase:

```python
@dataclass
class DiagnosisRow:
```

represents one diagnosis row returned to the frontend.

## 7. SQL Aggregation

Aggregation means summarizing rows.

Examples:

```text
COUNT(*)
COUNT(DISTINCT fsn)
COUNT(DISTINCT bin)
```

The diagnoses API uses aggregation to compute:

```text
failures
orders_impacted
distinct_fsns
distinct_bins
verdict
```

## 8. Frontend Data Fetching

The frontend calls the backend using:

```text
frontend/src/api.js
```

For diagnoses:

```javascript
fetchDiagnoses(warehouseId, windowDays)
```

## 9. React State

React state stores changing UI data.

In `DiagnosesTable.jsx`, state stores:

```text
rows
loading
error
window
logging
```

When `rows` changes, the table re-renders.

## Phase 4 Mental Model

```text
React table loads
  -> frontend calls fetchDiagnoses()
  -> backend router receives GET /api/diagnoses
  -> diagnosis service runs SQL
  -> StarRocks returns rows
  -> backend returns JSON
  -> React renders the table
```

Simple memory hook:

```text
button/load -> API call -> router -> service -> SQL -> JSON -> table
```
