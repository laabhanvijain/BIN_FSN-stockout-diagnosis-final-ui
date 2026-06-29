"""
backend/etl/sync.py
===================
Incremental ETL: StarRocks pendency_mv → NebulaGraph stockout space.

Schedule: 1-minute APScheduler cron (started in main.py lifespan).
Strategy: watermark-based (last seen updated_at). In-memory watermark resets
          on process restart — acceptable for the demo; production would
          persist it in a small KV store or a StarRocks table.

What gets synced
----------------
For every INF row newer than the watermark:
  Vertices (UPSERT):  FSN, BIN, Picker, Order, GRN
  Edges   (UPSERT):   FAILED_AT, PICKED_FROM, ASSIGNED_TO, RECEIVED_IN, PUTAWAY_TO

Idempotency: NebulaGraph INSERT VERTEX / INSERT EDGE with "IF NOT EXISTS" semantics
is achieved by using "INSERT VERTEX ... VALUES" which overwrites on re-run (upsert
by VID). Edges are inserted the same way — duplicate insertions overwrite properties.
"""

import datetime
import logging

from backend.config import settings
from backend.db.nebula import get_session
from backend.db.starrocks import get_connection

logger = logging.getLogger(__name__)

# In-memory watermark — reset to epoch on startup so first run always syncs all data.
_watermark: datetime.datetime = datetime.datetime(2000, 1, 1)


# ── SQL to fetch new rows ─────────────────────────────────────────────────────

_FETCH_SQL = """
SELECT
    reservation_warehouse_id  AS wh,
    picklist_source_location_label AS bin,
    picklist_item_fsn         AS fsn,
    picklist_assigned_to      AS picker,
    order_id,
    grn_id,
    updated_at
FROM pendency_mv
WHERE irt_ticket_id IS NOT NULL
  AND updated_at > %(watermark)s
ORDER BY updated_at
"""


# ── nGQL helpers ──────────────────────────────────────────────────────────────

def _esc(value: str) -> str:
    """Escape single quotes for embedding values in nGQL string literals."""
    return str(value).replace("'", "\\'")


def _bin_vid(wh: str, label: str) -> str:
    return f"{_esc(wh)}:{_esc(label)}"


def _upsert_vertices(session, rows: list[dict]) -> None:
    """Batch-upsert all vertex types for a chunk of rows."""
    if not rows:
        return

    fsn_vals, bin_vals, picker_vals, order_vals, grn_vals = [], [], [], [], []

    for r in rows:
        wh, bin_, fsn = _esc(r["wh"]), _esc(r["bin"]), _esc(r["fsn"])
        picker = _esc(r["picker"] or "")
        order = _esc(r["order_id"] or "")
        grn = _esc(r["grn_id"] or "")
        bin_vid = _bin_vid(r["wh"], r["bin"])

        fsn_vals.append(f'"{fsn}":("{fsn}")')
        bin_vals.append(f'"{bin_vid}":("{bin_}","{wh}")')
        if picker:
            picker_vals.append(f'"{picker}":("{picker}")')
        if order:
            order_vals.append(f'"{order}":("{order}")')
        if grn:
            grn_vals.append(f'"{grn}":("{grn}")')

    stmts = [
        f'INSERT VERTEX IF NOT EXISTS FSN(fsn) VALUES {",".join(fsn_vals)};',
        f'INSERT VERTEX IF NOT EXISTS BIN(label,warehouse_id) VALUES {",".join(bin_vals)};',
    ]
    if picker_vals:
        stmts.append(
            f'INSERT VERTEX IF NOT EXISTS Picker(picker_id) VALUES {",".join(picker_vals)};'
        )
    if order_vals:
        stmts.append(
            f'INSERT VERTEX IF NOT EXISTS `Order`(order_id) VALUES {",".join(order_vals)};'
        )
    if grn_vals:
        stmts.append(
            f'INSERT VERTEX IF NOT EXISTS GRN(grn_id) VALUES {",".join(grn_vals)};'
        )

    ngql = f"USE {settings.nebula_space};\n" + "\n".join(stmts)
    result = session.execute(ngql)
    if not result.is_succeeded():
        logger.error("Vertex upsert failed: %s", result.error_msg())


def _upsert_edges(session, rows: list[dict]) -> None:
    """Batch-upsert all edge types for a chunk of rows."""
    if not rows:
        return

    import time
    now_ms = int(time.time() * 1000)

    failed_at, picked_from, assigned_to, received_in, putaway_to = [], [], [], [], []

    for r in rows:
        fsn = _esc(r["fsn"])
        bin_vid = _bin_vid(r["wh"], r["bin"])
        picker = _esc(r["picker"] or "")
        order = _esc(r["order_id"] or "")
        grn = _esc(r["grn_id"] or "")

        failed_at.append(f'"{fsn}"->"{bin_vid}"@0:({now_ms})')
        if order:
            picked_from.append(f'"{order}"->"{bin_vid}"@0:()')
        if picker:
            assigned_to.append(f'"{picker}"->"{bin_vid}"@0:()')
        if grn:
            received_in.append(f'"{fsn}"->"{grn}"@0:()')
            putaway_to.append(f'"{grn}"->"{bin_vid}"@0:()')

    stmts = [
        f'INSERT EDGE IF NOT EXISTS FAILED_AT(last_seen) VALUES {",".join(failed_at)};',
    ]
    if picked_from:
        stmts.append(
            f'INSERT EDGE IF NOT EXISTS PICKED_FROM() VALUES {",".join(picked_from)};'
        )
    if assigned_to:
        stmts.append(
            f'INSERT EDGE IF NOT EXISTS ASSIGNED_TO() VALUES {",".join(assigned_to)};'
        )
    if received_in:
        stmts.append(
            f'INSERT EDGE IF NOT EXISTS RECEIVED_IN() VALUES {",".join(received_in)};'
        )
    if putaway_to:
        stmts.append(
            f'INSERT EDGE IF NOT EXISTS PUTAWAY_TO() VALUES {",".join(putaway_to)};'
        )

    ngql = f"USE {settings.nebula_space};\n" + "\n".join(stmts)
    result = session.execute(ngql)
    if not result.is_succeeded():
        logger.error("Edge upsert failed: %s", result.error_msg())


# ── main sync function ────────────────────────────────────────────────────────

def run_etl_sync() -> None:
    """
    Pull new INF rows from StarRocks since the last watermark,
    upsert vertices and edges into NebulaGraph, then advance the watermark.

    Swallows all exceptions — a single failed sync should not crash the
    APScheduler job or the FastAPI process.
    """
    global _watermark

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(_FETCH_SQL, {"watermark": _watermark.strftime("%Y-%m-%d %H:%M:%S")})
                rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            logger.debug("ETL sync: no new rows since %s", _watermark)
            return

        logger.info("ETL sync: %d new rows since %s", len(rows), _watermark)

        with get_session() as session:
            if session is None:
                logger.warning("ETL sync: NebulaGraph unavailable, skipping graph write")
                return

            _upsert_vertices(session, rows)
            _upsert_edges(session, rows)

        # Advance watermark to the latest updated_at in this batch
        latest = max(r["updated_at"] for r in rows)
        if isinstance(latest, str):
            latest = datetime.datetime.fromisoformat(latest)
        _watermark = latest
        logger.info("ETL sync: watermark advanced to %s", _watermark)

    except Exception:
        logger.exception("ETL sync: unexpected error (will retry next interval)")
