# LLD 06 · ETL

> Status: **DONE** (M4 · 2026-06-25). Source files: `backend/etl/sync.py`, `backend/db/starrocks.py`, `backend/db/nebula.py`.

---

## Design

| Aspect | Detail |
|--------|--------|
| Trigger | APScheduler `BackgroundScheduler`, `interval` job, `minutes=1` |
| Watermark | Module-level `datetime` in `sync.py`; reset to epoch on startup (first run always full-sync); advances to `max(updated_at)` of each batch |
| Source query | `SELECT … FROM pendency_mv WHERE irt_ticket_id IS NOT NULL AND updated_at > %(watermark)s` |
| Vertex upsert | `INSERT VERTEX IF NOT EXISTS` — NebulaGraph semantics: overwrites if VID exists |
| Edge upsert | `INSERT EDGE IF NOT EXISTS` — same semantics |
| Failure handling | All exceptions caught; logged; next tick retries. No partial-state corruption because every operation is idempotent |
| Graph unavailable | `get_session()` yields `None`; ETL logs a warning and returns without crashing |

---

## Files

### `backend/db/starrocks.py`
- `get_connection()` — opens a fresh `PyMySQL` connection per call with `DictCursor`.
- Short-lived connections are fine at demo scale. Production: swap for `DBUtils.PooledDB`.

### `backend/db/nebula.py`
- Module-level `ConnectionPool` singleton initialised by `init_nebula_pool()` at FastAPI startup.
- `get_session()` — context manager that borrows a session from the pool and releases it on exit.
- If pool is `None` (NebulaGraph down), `get_session()` yields `None` — callers check for `None`.

### `backend/etl/sync.py`
- `run_etl_sync()` — the scheduled job.
  1. Fetch rows from StarRocks newer than `_watermark`.
  2. Upsert vertices: `FSN`, `BIN` (VID = `wh:label`), `Picker`, `Order`, `GRN`.
  3. Upsert edges: `FAILED_AT`, `PICKED_FROM`, `ASSIGNED_TO`, `RECEIVED_IN`, `PUTAWAY_TO`.
  4. Advance `_watermark` to `max(updated_at)` of the batch.

### `backend/main.py` (updated)
- Switched to FastAPI `lifespan` context manager (replaces deprecated `on_event`).
- `init_nebula_pool()` called at startup.
- `BackgroundScheduler` started at startup, shutdown gracefully on exit.

---

## BIN VID in nGQL

```
"{wh}:{bin_label}"   →   e.g.  "WH-BLR-001:BIN-PHANTOM-A"
```

Same convention as the NebulaGraph schema (ADR-0003). Keeps SQL and graph consistent.

---

## Key Technical Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| Watermark in-memory | Module `datetime` | Persistent (DB/file) | Acceptable for demo; production note inline |
| `IF NOT EXISTS` on INSERT | Yes | Overwrite always | First run is a full sync; `IF NOT EXISTS` prevents redundant re-writes |
| Graph unavailable = warn, not crash | Warning + return | Raise exception | Graph signals are additive; SQL verdict still works without graph |
| APScheduler `BackgroundScheduler` | Background (thread-based) | `AsyncIOScheduler` | Simpler; ETL is not async; no event-loop coupling |
| FastAPI `lifespan` | `@asynccontextmanager` | `on_event` (deprecated) | `on_event` deprecated since FastAPI 0.93 |
