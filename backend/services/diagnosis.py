"""
backend/services/diagnosis.py
==============================
Core verdict engine — implements the PS validation SQL verbatim, then adds
a recovery-projection estimate for each (wh, bin, fsn) cluster.

Verdict rules (from the PS):
  DUAL             : distinct_fsns >= PHANTOM_THRESHOLD AND distinct_bins >= STOCKOUT_THRESHOLD
  PHANTOM_INVENTORY: distinct_fsns >= PHANTOM_THRESHOLD
  GENUINE_STOCKOUT : distinct_bins >= STOCKOUT_THRESHOLD
  AMBIGUOUS        : neither threshold crossed

Recovery projection:
  Estimated order-fill-rate recovery = orders_impacted / total_orders_wh * 100
  (total_orders_wh is the count of all distinct order_ids in the warehouse window,
   used as the denominator to convert raw impacted orders into a fill-rate delta.)
  At demo scale we approximate total_orders_wh as SUM(orders) across all diagnoses
  in the same warehouse — good enough for a relative ranking.
"""

import logging
from dataclasses import dataclass, field

from backend.config import settings
from backend.db.starrocks import get_connection

logger = logging.getLogger(__name__)


@dataclass
class DiagnosisRow:
    warehouse_id: str
    bin: str
    fsn: str
    failures: int
    orders_impacted: int
    distinct_fsns: int   # how many distinct FSNs failed in this BIN
    distinct_bins: int   # how many distinct BINs this FSN failed in
    verdict: str
    recovery_pct: float = 0.0           # estimated fill-rate delta (%)


# ── SQL (mirrors the PS validation query exactly) ─────────────────────────────

_VERDICT_SQL = """
WITH inf AS (
    SELECT
        reservation_warehouse_id          AS wh,
        picklist_source_location_label    AS bin,
        picklist_item_fsn                 AS fsn,
        COUNT(*)                          AS failures,
        COUNT(DISTINCT order_id)          AS orders
    FROM pendency_mv
    WHERE irt_ticket_id IS NOT NULL
      AND updated_at >= NOW() - INTERVAL %(window_days)s DAY
    GROUP BY 1, 2, 3
),
bin_sum AS (
    SELECT wh, bin,
           COUNT(DISTINCT fsn) AS distinct_fsns
    FROM inf
    GROUP BY 1, 2
),
fsn_sum AS (
    SELECT wh, fsn,
           COUNT(DISTINCT bin) AS distinct_bins
    FROM inf
    GROUP BY 1, 2
)
SELECT
    i.wh                AS warehouse_id,
    i.bin,
    i.fsn,
    i.failures,
    i.orders            AS orders_impacted,
    b.distinct_fsns,
    f.distinct_bins,
    CASE
        WHEN b.distinct_fsns >= %(phantom_thr)s AND f.distinct_bins >= %(stockout_thr)s
            THEN 'DUAL'
        WHEN b.distinct_fsns >= %(phantom_thr)s
            THEN 'PHANTOM_INVENTORY'
        WHEN f.distinct_bins >= %(stockout_thr)s
            THEN 'GENUINE_STOCKOUT'
        ELSE 'AMBIGUOUS'
    END AS verdict
FROM inf i
JOIN bin_sum b ON b.wh = i.wh AND b.bin = i.bin
JOIN fsn_sum f ON f.wh = i.wh AND f.fsn = i.fsn
ORDER BY i.orders DESC, i.failures DESC
"""


# ── recovery projection ───────────────────────────────────────────────────────

def _compute_recovery(rows: list[dict]) -> dict[str, float]:
    """
    Return a map of (wh, bin, fsn) → recovery_pct.

    recovery_pct = (orders_impacted / total_orders_in_wh) * 100

    We approximate total_orders_in_wh as the sum of orders_impacted for all
    rows in the same warehouse (conservative lower-bound; all impacted orders
    count once towards the fill-rate denominator).
    """
    wh_totals: dict[str, int] = {}
    for r in rows:
        wh_totals[r["warehouse_id"]] = (
            wh_totals.get(r["warehouse_id"], 0) + r["orders_impacted"]
        )

    result = {}
    for r in rows:
        total = wh_totals.get(r["warehouse_id"], 1) or 1
        pct = round(r["orders_impacted"] / total * 100, 1)
        result[(r["warehouse_id"], r["bin"], r["fsn"])] = pct
    return result


# ── public API ────────────────────────────────────────────────────────────────

def get_diagnoses(
    warehouse_id: str | None = None,
    window_days: int | None = None,
) -> list[DiagnosisRow]:
    """
    Run the PS verdict SQL and return a ranked list of DiagnosisRow objects.

    Args:
        warehouse_id: optional filter — if None, returns all warehouses.
        window_days:  lookback window in days (default from settings).
    """
    window = window_days or settings.diagnosis_window_days
    params = {
        "window_days": window,
        "phantom_thr": settings.phantom_fsn_threshold,
        "stockout_thr": settings.stockout_bin_threshold,
    }

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(_VERDICT_SQL, params)
                raw_rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to run verdict SQL")
        return []

    if not raw_rows:
        return []

    # Optional warehouse filter (done in Python to keep SQL generic)
    if warehouse_id:
        raw_rows = [r for r in raw_rows if r["warehouse_id"] == warehouse_id]

    recovery_map = _compute_recovery(raw_rows)

    # Build diagnosis rows (graph signals now queried dynamically by LLM agent)
    diagnoses = []
    for r in raw_rows:
        key = (r["warehouse_id"], r["bin"], r["fsn"])
        diagnoses.append(
            DiagnosisRow(
                warehouse_id=r["warehouse_id"],
                bin=r["bin"],
                fsn=r["fsn"],
                failures=r["failures"],
                orders_impacted=r["orders_impacted"],
                distinct_fsns=r["distinct_fsns"],
                distinct_bins=r["distinct_bins"],
                verdict=r["verdict"],
                recovery_pct=recovery_map.get(key, 0.0),
            )
        )

    logger.info(
        "Verdict SQL returned %d rows (window=%sd, wh=%s)",
        len(diagnoses), window, warehouse_id or "ALL",
    )
    return diagnoses
