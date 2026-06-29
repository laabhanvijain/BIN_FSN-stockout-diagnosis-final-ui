# backend/etl/sync.py — Code Walkthrough

> Source: `backend/etl/sync.py`, `backend/db/starrocks.py`, `backend/db/nebula.py`, `backend/main.py`
> Milestone: M4 · Last updated: 2026-06-25

## What it does

Every 60 seconds, pulls INF rows from StarRocks that are newer than an
in-memory watermark and upserts them into NebulaGraph as vertices + edges.

---

## File overview

```
backend/
├── db/
│   ├── starrocks.py   ← get_connection() — PyMySQL, DictCursor
│   └── nebula.py      ← ConnectionPool singleton + get_session() context manager
└── etl/
    └── sync.py        ← run_etl_sync() — the scheduled job
main.py                ← lifespan: init pool + start scheduler
```

---

## `backend/db/starrocks.py`

```python
def get_connection() -> pymysql.connections.Connection:
    return pymysql.connect(host=..., cursorclass=DictCursor)
```

Opens a fresh connection per call. `DictCursor` returns rows as `dict` instead of
tuples — makes downstream code readable (`row["fsn"]` vs `row[2]`).

**Why not a pool?** At demo scale, 1 connection/minute is negligible. A production
system would use `DBUtils.PooledDB` or SQLAlchemy's connection pool.

---

## `backend/db/nebula.py`

### Pool singleton

```python
_pool: ConnectionPool | None = None

def init_nebula_pool() -> None:
    global _pool
    if _pool is not None: return   # idempotent
    pool = ConnectionPool()
    ok = pool.init([(host, port)], config)
    _pool = pool if ok else None
```

Called once at FastAPI startup. If NebulaGraph is not reachable, `_pool` stays
`None` and all downstream calls degrade gracefully.

### `get_session()` context manager

```python
@contextmanager
def get_session():
    if _pool is None:
        yield None        # caller checks for None before using
        return
    session = _pool.get_session(user, password)
    try:
        yield session
    finally:
        session.release()  # always returns session to pool
```

**Why yield None instead of raising?** The graph signals are additive enrichments.
If NebulaGraph is down, the system still returns SQL-based verdicts — the graph
layer failing should never block the diagnoses API.

---

## `backend/etl/sync.py`

### Watermark

```python
_watermark: datetime = datetime(2000, 1, 1)   # reset on startup → full sync first run
```

### Source SQL

```sql
SELECT wh, bin, fsn, picker, order_id, grn_id, updated_at
FROM   pendency_mv
WHERE  irt_ticket_id IS NOT NULL      -- INF events only
  AND  updated_at > %(watermark)s     -- incremental
ORDER BY updated_at
```

### Vertex upserts

```
INSERT VERTEX IF NOT EXISTS FSN(fsn) VALUES "FSN-S1-001":("FSN-S1-001");
INSERT VERTEX IF NOT EXISTS BIN(label,warehouse_id) VALUES "WH-001:BIN-A":("BIN-A","WH-001");
```

BIN VID = `"wh:label"` — matches ADR-0003. `IF NOT EXISTS` makes re-runs safe.

### Edge upserts

```
INSERT EDGE IF NOT EXISTS FAILED_AT(last_seen) VALUES "FSN-S1-001"->"WH-001:BIN-A"@0:(1751000000000);
INSERT EDGE IF NOT EXISTS ASSIGNED_TO() VALUES "PKR-001"->"WH-001:BIN-A"@0:();
```

Ranking key `@0` is the edge rank — we use 0 for all edges (no multi-edge need).

### Error handling

```python
def run_etl_sync() -> None:
    try:
        ...
    except Exception:
        logger.exception("ETL sync: unexpected error (will retry next interval)")
```

Swallows all exceptions. The APScheduler job continues to fire even if one cycle
fails. Next tick is a fresh retry (watermark not advanced on failure).

---

## `backend/main.py` — lifespan integration

```python
@asynccontextmanager
async def lifespan(app):
    init_nebula_pool()
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_etl_sync, "interval", minutes=1)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

`BackgroundScheduler` runs ETL in a daemon thread — doesn't block the async
event loop. `wait=False` on shutdown avoids a 60-second hang on SIGTERM.

---

## Idempotency guarantee

| Operation | Why idempotent |
|-----------|----------------|
| Vertex upsert | `IF NOT EXISTS` — NebulaGraph ignores the insert if VID already exists |
| Edge upsert | Same — edge between same src/dst/@rank is overwritten with latest properties |
| Watermark advance | Only advances after a successful batch; failure = no advance = retry next tick |

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| In-memory watermark | Module `datetime` | Simplest for demo; full restart = harmless full re-sync |
| `BackgroundScheduler` (threads) | Not `AsyncIOScheduler` | ETL code is synchronous; no event-loop coupling |
| `IF NOT EXISTS` on inserts | Yes | Safe for re-runs; first run is always a full sync |
| Graph unavailable = degrade | `yield None` | Graph enrichment is optional; SQL verdict must always work |
| `lifespan` context manager | FastAPI 0.93+ pattern | `on_event` is deprecated |
