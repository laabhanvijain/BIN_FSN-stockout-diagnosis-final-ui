# Phase 3 Prerequisites

Phase 3 is about backend startup and configuration. Before reading the files,
understand these ideas:

1. Python import
2. Function
3. Class
4. Environment variable
5. HTTP server
6. FastAPI app
7. Middleware
8. Router
9. Connection factory
10. Connection pool
11. Background scheduler

## 1. Python Import

An import lets one Python file use code from another file or library.

Example:

```python
from backend.config import settings
```

Meaning:

```text
Use the settings object defined in backend/config.py.
```

## 2. Function

A function is a reusable block of code.

Example:

```python
def health():
    return {"status": "ok"}
```

Meaning:

```text
When this function is called, return a small health response.
```

## 3. Class

A class is a blueprint for structured data or behavior.

In Phase 3:

```python
class Settings(BaseSettings):
```

defines all configuration fields used by the backend.

## 4. Environment Variable

An environment variable is a runtime setting outside the code.

Example:

```text
STARROCKS_HOST=starrocks-fe
NEBULA_HOST=nebula-graphd
LLM_MODEL=llama3.1:8b
```

Why use environment variables?

```text
So the same code can run locally, in Docker, or in production with different
hostnames, ports, passwords, and model names.
```

## 5. HTTP Server

An HTTP server receives requests from clients.

Example:

```text
GET /health
GET /api/diagnoses
POST /api/ask
```

In this project, Uvicorn runs the FastAPI app.

## 6. FastAPI App

FastAPI is the Python web framework used by the backend.

The app object represents the backend service:

```python
app = FastAPI(...)
```

All backend routes are attached to this app.

## 7. Middleware

Middleware is code that runs around requests.

In this project, CORS middleware allows the browser frontend to call the backend.

CORS means Cross-Origin Resource Sharing.

Beginner meaning:

```text
Browser security rules need permission before frontend and backend on different
origins can talk.
```

## 8. Router

A router groups API endpoints.

This project has routers for:

```text
diagnoses
ask
feedback
```

They are mounted under:

```text
/api
```

## 9. Connection Factory

A connection factory is a function that creates database connections.

Example:

```python
get_connection()
```

In this project, `backend/db/starrocks.py` creates StarRocks connections.

## 10. Connection Pool

A connection pool keeps reusable database/network connections.

This is useful when opening a connection is expensive.

In this project:

```text
NebulaGraph uses a shared connection pool.
StarRocks uses short-lived per-call connections.
```

## 11. Background Scheduler

A background scheduler runs work periodically without a user request.

In this project:

```text
APScheduler runs the ETL sync every 1 minute.
```

That means even if no user clicks anything, the backend periodically syncs
StarRocks rows into NebulaGraph.

## Phase 3 Mental Model

When the backend starts:

```text
load settings
create FastAPI app
initialize NebulaGraph pool
start 1-minute ETL scheduler
register API routers
serve requests
```

Simple memory hook:

```text
config -> app startup -> DB clients -> routers -> scheduler
```
