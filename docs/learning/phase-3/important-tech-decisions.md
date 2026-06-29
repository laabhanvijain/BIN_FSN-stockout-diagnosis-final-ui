# Phase 3 Important Technical Decisions
**routers = receive HTTP requests**
**services = do the actual work**
**db = connect to databases**

backend/routers/
  -> "Someone called /api/diagnoses. What should I do?"

backend/services/
  -> "Here is how to compute diagnoses, query graph signals, run the assistant, or manage feedback."

backend/db/
  -> "Here is how to connect to StarRocks or NebulaGraph."


  
This file captures the important backend startup and configuration decisions.

## Decision 1: Centralize Config In `backend/config.py`

### Choice

Use one `Settings` class based on `pydantic-settings`.

### Why

The backend needs many runtime values:

```text
StarRocks host/port/user/password/database
NebulaGraph host/port/user/password/space
LLM base URL/model
diagnosis thresholds
assistant timeouts
```

Centralizing them avoids hardcoding scattered constants across the codebase.

### Trade-Off

This is simple and good for this project. In a larger production system, config
might be split by environment, secret manager, or deployment platform.

## Decision 2: Use Environment Variables With Defaults

### Choice

Give every setting a default, but allow `.env` or environment variables to
override it.

### Why

This lets the same code run in different environments:

```text
local machine -> localhost
Docker Compose -> service names like starrocks-fe and nebula-graphd
production -> managed hostnames/secrets
```

### Trade-Off

Defaults are convenient for demos, but production must manage secrets carefully.

## Decision 3: StarRocks Uses Short-Lived Connections

### Choice

`backend/db/starrocks.py` opens a new PyMySQL connection on each call.

### Why

This is simple and acceptable at demo scale.

### Trade-Off

Opening a database connection repeatedly can be inefficient under high traffic.

Production improvement:

```text
replace with a real connection pool
```

Important note:

```text
The file-level docstring says pool-like singleton, but the actual function opens
a new connection each call. The function docstring matches the real behavior.
```

## Decision 4: NebulaGraph Uses A Shared Connection Pool

### Choice

Initialize a module-level NebulaGraph connection pool once at startup.

### Why

NebulaGraph client usage is pool-oriented. Reusing sessions avoids reconnecting
for every graph query.

### Trade-Off

Callers must handle the case where the pool is unavailable. This project does
that by allowing `get_session()` to yield `None`.

## Decision 5: Initialize NebulaGraph During FastAPI Lifespan

### Choice

Call:

```python
init_nebula_pool()
```

inside the FastAPI lifespan startup.

### Why

The graph pool should be ready before request handlers or the ETL job need it.

### Trade-Off

If graph initialization fails, the backend still starts. This is good for
fallback behavior, but graph signals may be unavailable.

## Decision 6: Run ETL With APScheduler Inside The Backend

### Choice

Start a `BackgroundScheduler` in `backend/main.py` and run:

```text
run_etl_sync every 1 minute
```

### Why

It keeps the local demo simple. No separate worker service is required.

### Trade-Off

In production, embedding scheduled jobs inside an API process can be risky:

```text
multiple backend replicas may run duplicate jobs
job failures share process with API server
long ETL work can compete with API resources
```

Production improvement:

```text
move ETL to a separate worker/scheduler service
```

## Decision 7: Use Permissive CORS For Demo

### Choice

Use:

```python
allow_origins=["*"]
```

### Why

This avoids frontend/backend browser issues during local demo.

### Trade-Off

This is too open for production. Production should restrict allowed origins to
the real frontend URL.

## Decision 8: Mount Routers Under `/api`

### Choice

Mount:

```text
diagnoses
ask
feedback
```

under:

```text
/api
```

### Why

This cleanly separates backend API routes from frontend/static routes and keeps
the frontend proxy simple.

## Decision 9: Keep `/health` Simple

### Choice

Return:

```json
{"status": "ok"}
```

### Why

This gives Docker, smoke tests, or humans a quick liveness check.

### Trade-Off

It only checks that the app process is alive. It does not verify StarRocks,
NebulaGraph, or Ollama health.

Production improvement:

```text
add deeper readiness checks for dependencies
```
