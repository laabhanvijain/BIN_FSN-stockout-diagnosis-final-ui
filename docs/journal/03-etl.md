# 03 · ETL (StarRocks -> NebulaGraph)

> 1-minute sync notes. Milestone: M4. Detail: [../deliverables/LLD/06-etl.md](../deliverables/LLD/06-etl.md).

_Status: M4 (ETL sync) done 2026-06-25._

---

## 2026-06-25 — M4 complete: ETL sync (StarRocks → NebulaGraph)

### What was done

**`backend/db/starrocks.py`**
- `get_connection()` — PyMySQL connection with `DictCursor`. Short-lived per call.

**`backend/db/nebula.py`**
- Module-level `ConnectionPool` singleton. `init_nebula_pool()` called at FastAPI startup.
- `get_session()` context manager — yields `None` gracefully if pool not ready.

**`backend/etl/sync.py`**
- `run_etl_sync()`: fetch INF rows newer than `_watermark` → upsert 5 vertex types
  (FSN, BIN, Picker, Order, GRN) + 5 edge types (FAILED_AT, PICKED_FROM, ASSIGNED_TO,
  RECEIVED_IN, PUTAWAY_TO) → advance watermark to `max(updated_at)`.
- All exceptions swallowed — a failed sync never crashes the FastAPI process.

**`backend/main.py`** (updated)
- Migrated from deprecated `on_event` to FastAPI `lifespan` context manager.
- Calls `init_nebula_pool()` and starts `BackgroundScheduler` on startup.
- Graceful scheduler shutdown on process exit.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| In-memory watermark | Module `datetime` | Simplest for demo; production note documented inline |
| `IF NOT EXISTS` upserts | Yes | First run is a full sync; avoids redundant re-writes |
| Graph unavailable = warn+return | Not raise | Graph is additive; SQL verdict still works alone |
| `BackgroundScheduler` (thread) | Thread-based | ETL is sync; no event-loop coupling needed |
| FastAPI `lifespan` | `@asynccontextmanager` | `on_event` deprecated since FastAPI 0.93 |

### Files changed

- Created: `backend/db/starrocks.py`, `backend/db/nebula.py`, `backend/etl/sync.py`
- Updated: `backend/main.py`

### Status: committed 2026-06-25

<!-- ## YYYY-MM-DD — <what happened> -->
