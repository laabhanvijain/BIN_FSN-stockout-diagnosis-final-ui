# Phase 4 Correct Answers

Use this after answering the Phase 4 checkpoint questions.

## 1. What Route Does The Frontend Call For Diagnoses?

The frontend calls:

```text
GET /api/diagnoses
```

through:

```text
frontend/src/api.js
```

Function:

```javascript
fetchDiagnoses(warehouseId, windowDays)
```

## 2. Which Backend Router Receives It?

The request is handled by:

```text
backend/routers/diagnoses.py
```

Endpoint:

```python
@router.get("/diagnoses")
def diagnoses_endpoint(...):
```

Because `main.py` mounts the router under `/api`, the full path is:

```text
/api/diagnoses
```

## 3. Which Service Computes The Verdict?

The verdict is computed in:

```text
backend/services/diagnosis.py
```

Main function:

```python
get_diagnoses(...)
```

Core SQL:

```python
_VERDICT_SQL
```

## 4. What Counts Are Needed For The Verdict?

The two key counts are:

```text
distinct_fsns
distinct_bins
```

Meaning:

```text
distinct_fsns = how many different FSNs failed in this BIN
distinct_bins = how many different BINs this FSN failed across
```

Verdict rules:

```text
distinct_fsns >= 3 AND distinct_bins >= 2 -> DUAL
distinct_fsns >= 3                        -> PHANTOM_INVENTORY
distinct_bins >= 2                        -> GENUINE_STOCKOUT
else                                      -> AMBIGUOUS
```

## 5. What Does The Frontend Render From The Response?

The frontend renders rows in:

```text
frontend/src/DiagnosesTable.jsx
```

Important displayed fields:

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
Action button
```

The verdict is displayed as a badge, such as:

```text
Phantom Inventory
Genuine Stockout
Dual
Ambiguous
```
