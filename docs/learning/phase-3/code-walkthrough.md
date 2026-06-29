# Phase 3 Code Walkthrough

Phase 3 files:

1. `backend/main.py`
2. `backend/config.py`
3. `backend/db/starrocks.py`
4. `backend/db/nebula.py`
5. `backend/requirements.txt`

This phase explains how the backend starts, how it reads configuration, and how
it connects to StarRocks and NebulaGraph.

## File 1: `backend/config.py`

### Purpose

This file centralizes backend configuration.

It defines:

```python
class Settings(BaseSettings):
```

and then creates:

```python
settings = Settings()
```

The rest of the backend imports `settings` instead of hardcoding hostnames,
ports, thresholds, and model names.

## Important Dependency: `pydantic-settings`

`Settings` extends:

```python
BaseSettings
```

from:

```python
pydantic_settings
```

This lets the app read settings from:

1. default values in code
2. environment variables
3. `.env` file

## StarRocks Settings

```python
starrocks_host: str = "localhost"
starrocks_port: int = 9030
starrocks_user: str = "root"
starrocks_password: str = ""
starrocks_database: str = "hl_customer_outbound"
```

Meaning:

```text
Use StarRocks at localhost:9030 by default.
Connect as root.
Use the hl_customer_outbound database.
```

In Docker, these can be overridden by environment variables, for example:

```text
STARROCKS_HOST=starrocks-fe
```

## NebulaGraph Settings

```python
nebula_host: str = "localhost"
nebula_port: int = 9669
nebula_user: str = "root"
nebula_password: str = "nebula"
nebula_space: str = "stockout"
```

Meaning:

```text
Use NebulaGraph at localhost:9669 by default.
Use graph space stockout.
```

## LLM Settings

```python
llm_base_url: str = "http://localhost:11434/v1"
llm_api_key: str = "ollama"
llm_model: str = "llama3.1:8b"
```

Meaning:

```text
Use local Ollama through its OpenAI-compatible endpoint.
Default model is llama3.1:8b.
```

These settings matter later in the assistant phase.

## Ask Budgets

```python
ask_total_timeout_ms: int = 10000
ask_thorough_timeout_ms: int = 30000
ask_max_iterations: int = 12
ask_per_query_timeout_ms: int = 5000
```

These control how much time and how many tool iterations the assistant can use.

Phase 3 does not deeply explain the assistant yet, but this shows that runtime
behavior is configurable.

## Diagnosis Thresholds

```python
diagnosis_window_days: int = 1
phantom_fsn_threshold: int = 3
stockout_bin_threshold: int = 2
```

These are the Phase 1 rules made configurable.

Meaning:

```text
look back 1 day
3 distinct FSNs -> phantom threshold
2 distinct BINs -> stockout threshold
```

## `.env` Loading

```python
class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"
```

This tells Pydantic to read a `.env` file if present.

## File 2: `backend/db/starrocks.py`

### Purpose

This file creates StarRocks database connections.

It imports:

```python
import pymysql
from backend.config import settings
```

`PyMySQL` is used because StarRocks exposes a MySQL-compatible protocol.

## `get_connection()`

```python
def get_connection() -> pymysql.connections.Connection:
```

This function opens a new connection to StarRocks.

Important settings used:

```python
host=settings.starrocks_host
port=settings.starrocks_port
user=settings.starrocks_user
password=settings.starrocks_password
database=settings.starrocks_database
```

It also sets:

```python
cursorclass=pymysql.cursors.DictCursor
```

Meaning query results come back like dictionaries:

```python
{"bin": "BIN-A", "fsn": "FSN-1"}
```

instead of tuples:

```python
("BIN-A", "FSN-1")
```

## Important Observation

The file-level docstring says:

```text
Returns a connection pool-like singleton using a simple cached connection.
```

But the actual function opens a new connection on every call.

The function docstring correctly says:

```text
Open a new PyMySQL connection to StarRocks on every call.
```

So the actual behavior is:

```text
short-lived per-call StarRocks connections
```

For demo scale this is fine. In production, a real connection pool would be
better.

## File 3: `backend/db/nebula.py`

### Purpose

This file manages NebulaGraph sessions.

Unlike StarRocks, NebulaGraph uses a shared connection pool.

Important module-level variable:

```python
_pool: ConnectionPool | None = None
```

This is a singleton-like shared pool.

## `init_nebula_pool()`

This function is called once at backend startup.

It:

1. checks if `_pool` already exists
2. creates Nebula config
3. sets max pool size to 10
4. initializes a `ConnectionPool`
5. stores it in `_pool`

Important line:

```python
ok = pool.init([(settings.nebula_host, settings.nebula_port)], config)
```

Meaning:

```text
Connect the pool to the configured NebulaGraph host and port.
```

If initialization fails, it logs an error and leaves `_pool` as `None`.

## `get_session()`

```python
@contextmanager
def get_session():
```

This is a context manager.

Usage:

```python
with get_session() as session:
    result = session.execute("...")
```

If the pool is not initialized:

```python
yield None
```

This means graph callers must handle the graph being unavailable.

If the pool exists:

```python
session = _pool.get_session(settings.nebula_user, settings.nebula_password)
```

Then after the caller finishes:

```python
session.release()
```

This returns the session to the pool.

## File 4: `backend/main.py`

### Purpose

This is the FastAPI application entry point.

It defines:

```python
app = FastAPI(...)
```

and wires together:

```text
startup lifecycle
CORS middleware
API routers
health endpoint
ETL scheduler
NebulaGraph pool
```

## Imports

Important imports:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.nebula import init_nebula_pool
from backend.etl.sync import run_etl_sync
```

Meaning:

```text
FastAPI creates the app.
CORS allows browser/frontend requests.
APScheduler runs ETL periodically.
init_nebula_pool prepares graph connections.
run_etl_sync copies StarRocks rows into NebulaGraph.
```

## Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
```

The lifespan function runs startup code before the app serves requests and
shutdown code when the app stops.

Startup:

```python
init_nebula_pool()

scheduler = BackgroundScheduler()
scheduler.add_job(run_etl_sync, "interval", minutes=1, id="etl_sync")
scheduler.start()
```

Meaning:

```text
Initialize NebulaGraph pool.
Create scheduler.
Run ETL sync every 1 minute.
Start scheduler.
```

Shutdown:

```python
scheduler.shutdown(wait=False)
```

Meaning:

```text
Stop the background scheduler when the backend shuts down.
```

## FastAPI App

```python
app = FastAPI(
    title="BIN-FSN Stockout Diagnosis",
    description=...,
    version="0.1.0",
    lifespan=lifespan,
)
```

This creates the backend application and attaches the startup/shutdown lifecycle.

## CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Meaning:

```text
Allow browser clients to call this backend.
```

Important production note:

```text
allow_origins=["*"] is permissive.
For production, restrict it to the real frontend origin.
```

## Routers

```python
from backend.routers import diagnoses, ask, feedback
app.include_router(diagnoses.router, prefix="/api", tags=["diagnoses"])
app.include_router(ask.router, prefix="/api", tags=["assistant"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
```

Meaning:

```text
Mount diagnoses endpoints under /api.
Mount assistant endpoints under /api.
Mount feedback endpoints under /api.
```

So later endpoints become:

```text
/api/diagnoses
/api/ask
/api/feedback
```

## Health Endpoint

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

This is a simple endpoint to check whether the backend is alive.

## File 5: `backend/requirements.txt`

### Purpose

This lists Python dependencies.

Important packages:

| Package | Why It Exists |
|---|---|
| `fastapi` | Backend API framework. |
| `uvicorn[standard]` | Runs the FastAPI app. |
| `pydantic` | Data validation support. |
| `pydantic-settings` | Environment/settings loading. |
| `PyMySQL` | StarRocks connection through MySQL protocol. |
| `nebula3-python` | NebulaGraph Python client. |
| `openai` | Calls Ollama through OpenAI-compatible API. |
| `apscheduler` | Runs ETL sync every minute. |
| `python-dotenv` | Supports `.env` loading. |

## Phase 3 Runtime Flow

When the backend starts:

```text
Python imports backend/main.py
  -> backend/config.py creates settings
  -> FastAPI app is created
  -> lifespan startup runs
  -> init_nebula_pool() initializes graph pool
  -> APScheduler starts run_etl_sync every 1 minute
  -> routers are mounted under /api
  -> /health becomes available
  -> backend serves requests
```

When the backend stops:

```text
lifespan shutdown runs
  -> scheduler shuts down
```

## Phase 3 Takeaways

1. `backend/config.py` centralizes runtime settings.
2. `backend/main.py` creates and wires the FastAPI app.
3. StarRocks uses new short-lived PyMySQL connections.
4. NebulaGraph uses a shared connection pool.
5. APScheduler runs ETL sync every 1 minute.
6. Routers are mounted under `/api`.
7. `/health` is the simple backend liveness endpoint.
