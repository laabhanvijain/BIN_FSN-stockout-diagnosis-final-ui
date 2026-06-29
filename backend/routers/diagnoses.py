"""
backend/routers/diagnoses.py
=============================
GET /api/diagnoses — returns ranked verdict rows for a warehouse.

Query params:
  warehouse_id  str   optional — filter to one dark store
  window_days   int   optional — lookback window (default: settings.diagnosis_window_days)

Response: list of DiagnosisResponse objects (JSON).

Graph signals (picker_concentration, shared_grn, stocktake_done) are left as
empty dicts in this milestone and filled by the M6 graph enrichment layer.
"""

from dataclasses import asdict

from fastapi import APIRouter, Query

from backend.services.diagnosis import get_diagnoses

router = APIRouter()


@router.get("/diagnoses")
def diagnoses_endpoint(
    warehouse_id: str | None = Query(default=None, description="Filter to one warehouse"),
    window_days: int = Query(default=1, ge=1, le=30, description="Lookback window in days"),
):
    """
    Run the PS verdict SQL and return ranked (wh, bin, fsn) diagnosis rows.

    Each row contains:
    - verdict: PHANTOM_INVENTORY | GENUINE_STOCKOUT | DUAL | AMBIGUOUS
    - distinct_fsns / distinct_bins: the counts that drove the verdict
    - failures / orders_impacted: raw event counts
    - recovery_pct: estimated fill-rate recovery if the root cause is fixed
    - graph_signals: enrichment from NebulaGraph (empty until M6)
    """
    rows = get_diagnoses(warehouse_id=warehouse_id, window_days=window_days)
    return [asdict(r) for r in rows]
