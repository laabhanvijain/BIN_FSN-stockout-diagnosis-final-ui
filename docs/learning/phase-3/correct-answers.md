# Phase 3 Correct Answers

Use this file after answering the Phase 3 checkpoint questions.

## 1. What Does `backend/main.py` Create?

`backend/main.py` creates the main FastAPI backend application:

```python
app = FastAPI(...)
```

It also wires:

```text
FastAPI lifespan startup/shutdown
CORS middleware
/api routers
/health endpoint
NebulaGraph pool initialization
1-minute ETL scheduler
```

## 2. What Is The Purpose Of `Settings` In `backend/config.py`?

`Settings` centralizes runtime configuration.

It stores values such as:

```text
StarRocks host/port/database
NebulaGraph host/port/space
LLM base URL/model
diagnosis thresholds
assistant timeouts
```

It reads defaults from code and can override them using environment variables or
a `.env` file.

## 3. Why Does The Backend Need A StarRocks Connection?

The backend needs StarRocks to query table data.

Main uses:

```text
compute diagnosis verdicts from pendency_mv
read/write recommendation_log
support feedback calculations
feed ETL source rows into NebulaGraph
```

StarRocks is the source for count-based diagnosis.

## 4. Why Does The Backend Need A NebulaGraph Connection?

The backend needs NebulaGraph to query relationship-based evidence.

Examples:

```text
picker concentration
shared GRN batch
stocktake/variance signals
graph evidence for assistant answers
```

NebulaGraph is the graph enrichment layer.

## 5. What Background Job Is Scheduled On Startup?

The backend schedules:

```text
run_etl_sync
```

to run every:

```text
1 minute
```

Purpose:

```text
sync recent StarRocks rows into NebulaGraph so graph signals stay updated.
```
