"""
backend/services/graph.py
=========================
Graph query helper functions for the LLM agent.

These functions are available for the agent to query graph signals dynamically,
rather than pre-computing them for every diagnosis row.

The LLM decides which signals to query based on the question and context.
"""

import logging
from collections import Counter

from backend.config import settings
from backend.db.nebula import get_session

logger = logging.getLogger(__name__)

# Picker concentration threshold: if one picker accounts for >= this fraction
# of ASSIGNED_TO edges on a BIN, flag as picker-driven.
PICKER_CONCENTRATION_THRESHOLD = 0.7


# ── nGQL helpers ──────────────────────────────────────────────────────────────

def _exec(session, ngql: str):
    """Execute nGQL against the stockout space and return the ResultSet."""
    full = f"USE {settings.nebula_space};\n{ngql}"
    result = session.execute(full)
    if not result.is_succeeded():
        logger.warning("nGQL failed: %s | %s", ngql[:120], result.error_msg())
        return None
    return result


def _bin_vid(wh: str, label: str) -> str:
    return f"{wh}:{label}"


# ── signal: picker concentration ──────────────────────────────────────────────

def get_picker_concentration(wh: str, bin_label: str) -> dict:
    """
    Return picker-concentration signal for a BIN.

    nGQL: find all Picker nodes with ASSIGNED_TO edge to this BIN,
    count occurrences, return the dominant picker's share.

    Returns:
        {} if graph unavailable or no picker edges exist
        {"picker_concentration": float, "dominant_picker": str} otherwise
    """
    with get_session() as session:
        if session is None:
            return {}

        vid = _bin_vid(wh, bin_label)
        ngql = (
            f'MATCH (p:Picker)-[:ASSIGNED_TO]->(b:BIN) '
            f'WHERE id(b) == "{vid}" '
            f'RETURN p.Picker.picker_id AS picker_id'
        )
        result = _exec(session, ngql)
        if result is None or result.row_size() == 0:
            return {}

        picker_ids = [
            str(result.row_values(i)[0]) for i in range(result.row_size())
        ]
        counts = Counter(picker_ids)
        total = sum(counts.values())
        dominant_picker, dominant_count = counts.most_common(1)[0]
        concentration = round(dominant_count / total, 3)

        if concentration >= PICKER_CONCENTRATION_THRESHOLD:
            return {
                "picker_concentration": concentration,
                "dominant_picker": dominant_picker,
            }
        return {}


# ── signal: shared GRN batch ──────────────────────────────────────────────────

def get_shared_grn(wh: str, bin_label: str) -> dict:
    """
    Return shared-GRN signal for a BIN.

    nGQL: from each FSN that has a FAILED_AT edge to this BIN, follow
    RECEIVED_IN to a GRN. If all failing FSNs share one GRN → flag.

    Returns:
        {} if graph unavailable, no GRN edges, or FSNs use multiple GRNs
        {"shared_grn": "<grn_id>", "fsn_count": int} if all FSNs share one GRN
    """
    with get_session() as session:
        if session is None:
            return {}

        vid = _bin_vid(wh, bin_label)
        # Two-hop: FSN -[FAILED_AT]-> BIN  &  FSN -[RECEIVED_IN]-> GRN
        ngql = (
            f'MATCH (f:FSN)-[:FAILED_AT]->(b:BIN), (f)-[:RECEIVED_IN]->(g:GRN) '
            f'WHERE id(b) == "{vid}" '
            f'RETURN f.FSN.fsn AS fsn, g.GRN.grn_id AS grn_id'
        )
        result = _exec(session, ngql)
        if result is None or result.row_size() == 0:
            return {}

        grn_ids = set()
        fsn_count = 0
        for i in range(result.row_size()):
            grn_ids.add(str(result.row_values(i)[1]))
            fsn_count += 1

        if len(grn_ids) == 1:
            return {"shared_grn": grn_ids.pop(), "fsn_count": fsn_count}
        return {}


# ── signal: stocktake already done ───────────────────────────────────────────

def get_stocktake_done(wh: str, bin_label: str) -> dict:
    """
    Return stocktake signal for a BIN.

    nGQL: check if the BIN node has an outgoing STOCKTAKE edge to any Variance.

    Returns:
        {} if no STOCKTAKE edge
        {"stocktake_done": True} if at least one STOCKTAKE edge exists
    """
    with get_session() as session:
        if session is None:
            return {}

        vid = _bin_vid(wh, bin_label)
        ngql = (
            f'MATCH (b:BIN)-[s:STOCKTAKE]->(v:Variance) '
            f'WHERE id(b) == "{vid}" '
            f'RETURN s.STOCKTAKE.done_at AS done_at LIMIT 1'
        )
        result = _exec(session, ngql)
        if result is None or result.row_size() == 0:
            return {}

        return {"stocktake_done": True}


# ── signal: ATP proxy (stub) ──────────────────────────────────────────────────

def get_atp_proxy(distinct_bins: int) -> dict:
    """
    Conservative ATP cross-check stub.

    A real implementation queries the inventory/ATP service. Here we proxy:
    if distinct_bins >= STOCKOUT_THRESHOLD, the item is failing in multiple
    locations → very likely depleted → ATP is probably 0.

    Returns {"atp_likely_zero": True} for GENUINE_STOCKOUT candidates.
    """
    if distinct_bins >= settings.stockout_bin_threshold:
        return {"atp_likely_zero": True}
    return {}


# ── Note: These functions are now called dynamically by the LLM agent ────────
# The agent queries graph signals on-demand based on the question,
# rather than pre-computing them for every diagnosis row.
