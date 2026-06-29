"""
backend/services/feedback.py
=============================
Closed-loop feedback service over recommendation_log.

Lifecycle of a recommendation:
  suggested → acknowledged → executed → verified

At each status transition we capture additional data:
  suggested   : failures_before is set from live pendency_mv count
  executed    : failures_after is set from live pendency_mv count;
                failures_ceased = failures_before - failures_after is computed
  verified    : resolved_at timestamp is set

The key metric is failures_ceased — how many INF events stopped after the
action was taken. A positive value confirms the loop closed.
"""

import datetime
import logging

import pymysql

from backend.config import settings
from backend.db.starrocks import get_connection

logger = logging.getLogger(__name__)

# Valid status transitions (from → to)
VALID_TRANSITIONS: dict[str, str] = {
    "suggested": "acknowledged",
    "acknowledged": "executed",
    "executed": "verified",
}

# Derived action from verdict
VERDICT_TO_ACTION: dict[str, str] = {
    "PHANTOM_INVENTORY": "stocktake",
    "GENUINE_STOCKOUT": "replenish",
    "DUAL": "stocktake + replenish",
    "AMBIGUOUS": "investigate",
}


# ── live failure count ────────────────────────────────────────────────────────

def _live_failures(conn, warehouse_id: str, bin_label: str, fsn: str) -> int:
    """Count current open INF events for a (wh, bin, fsn) triple."""
    sql = """
        SELECT COUNT(*) AS cnt
        FROM pendency_mv
        WHERE reservation_warehouse_id = %(wh)s
          AND picklist_source_location_label = %(bin)s
          AND picklist_item_fsn = %(fsn)s
          AND irt_ticket_id IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"wh": warehouse_id, "bin": bin_label, "fsn": fsn})
        row = cur.fetchone()
    return int(row["cnt"]) if row else 0


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_recommendations(warehouse_id: str | None = None) -> list[dict]:
    """
    Return all recommendation_log rows, optionally filtered by warehouse.
    Computes `failures_ceased` inline for rows with both before and after values.
    """
    sql = "SELECT * FROM recommendation_log"
    params: dict = {}
    if warehouse_id:
        sql += " WHERE warehouse_id = %(wh)s"
        params["wh"] = warehouse_id
    sql += " ORDER BY suggested_at DESC"

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to list recommendations")
        return []

    # Compute failures_ceased for rows that have both values
    for r in rows:
        if r.get("failures_before") is not None and r.get("failures_after") is not None:
            r["failures_ceased"] = r["failures_before"] - r["failures_after"]
        else:
            r["failures_ceased"] = None
        # Serialize datetime fields to ISO strings for JSON
        for field in ("suggested_at", "resolved_at"):
            if isinstance(r.get(field), datetime.datetime):
                r[field] = r[field].isoformat()

    return rows


def create_recommendation(
    warehouse_id: str,
    bin_label: str,
    fsn: str,
    verdict: str,
    evidence_ref: str = "",
) -> dict:
    """
    Create a new recommendation_log row.
    Captures failures_before from live pendency_mv count at creation time.
    """
    action = VERDICT_TO_ACTION.get(verdict, "investigate")
    now = datetime.datetime.utcnow()

    try:
        conn = get_connection()
        try:
            failures_before = _live_failures(conn, warehouse_id, bin_label, fsn)
            sql = """
                INSERT INTO recommendation_log
                  (warehouse_id, bin, fsn, verdict, action, status,
                   suggested_at, evidence_ref, failures_before)
                VALUES
                  (%(wh)s, %(bin)s, %(fsn)s, %(verdict)s, %(action)s, 'suggested',
                   %(now)s, %(evidence_ref)s, %(failures_before)s)
            """
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "wh": warehouse_id,
                    "bin": bin_label,
                    "fsn": fsn,
                    "verdict": verdict,
                    "action": action,
                    "now": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "evidence_ref": evidence_ref,
                    "failures_before": failures_before,
                })
            conn.commit()
            # StarRocks doesn't return lastrowid reliably; fetch the latest row
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM recommendation_log "
                    "WHERE warehouse_id=%(wh)s AND bin=%(bin)s AND fsn=%(fsn)s "
                    "ORDER BY suggested_at DESC LIMIT 1",
                    {"wh": warehouse_id, "bin": bin_label, "fsn": fsn},
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to create recommendation")
        raise

    row["failures_ceased"] = None
    for field in ("suggested_at", "resolved_at"):
        if isinstance(row.get(field), datetime.datetime):
            row[field] = row[field].isoformat()
    return row


def advance_status(rec_id: int, new_status: str) -> dict:
    """
    Advance a recommendation's status through the defined lifecycle.
    On 'executed': captures failures_after from live pendency_mv.
    On 'verified': sets resolved_at timestamp.

    Raises ValueError for invalid transitions or unknown IDs.
    """
    try:
        conn = get_connection()
        try:
            # Fetch current row
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM recommendation_log WHERE id = %(id)s",
                    {"id": rec_id},
                )
                row = cur.fetchone()

            if not row:
                raise ValueError(f"Recommendation {rec_id} not found")

            current_status = row["status"]
            expected_next = VALID_TRANSITIONS.get(current_status)
            if new_status != expected_next:
                raise ValueError(
                    f"Invalid transition: {current_status} → {new_status}. "
                    f"Expected next: {expected_next}"
                )

            updates: dict = {"status": new_status}

            if new_status == "executed":
                failures_after = _live_failures(
                    conn, row["warehouse_id"], row["bin"], row["fsn"]
                )
                updates["failures_after"] = failures_after

            if new_status == "verified":
                updates["resolved_at"] = datetime.datetime.utcnow().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
            updates["id"] = rec_id
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE recommendation_log SET {set_clause} WHERE id = %(id)s",
                    updates,
                )
            conn.commit()

            # Re-fetch updated row
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM recommendation_log WHERE id = %(id)s",
                    {"id": rec_id},
                )
                row = cur.fetchone()
        finally:
            conn.close()
    except ValueError:
        raise
    except Exception:
        logger.exception("Failed to advance recommendation status")
        raise

    if row.get("failures_before") is not None and row.get("failures_after") is not None:
        row["failures_ceased"] = row["failures_before"] - row["failures_after"]
    else:
        row["failures_ceased"] = None

    for field in ("suggested_at", "resolved_at"):
        if isinstance(row.get(field), datetime.datetime):
            row[field] = row[field].isoformat()

    return row
