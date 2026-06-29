"""
backend/routers/feedback.py
============================
Three endpoints for the closed-loop recommendation feedback system:

  GET  /api/feedback                   — list all recommendations (+ failures_ceased)
  POST /api/feedback                   — create a new recommendation from a verdict
  PATCH /api/feedback/{id}/status      — advance status through the lifecycle
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.feedback import (
    advance_status,
    create_recommendation,
    list_recommendations,
)

router = APIRouter()


# ── request / response models ─────────────────────────────────────────────────

class CreateRecommendationRequest(BaseModel):
    warehouse_id: str
    bin: str
    fsn: str
    verdict: str = Field(..., pattern=r"^(PHANTOM_INVENTORY|GENUINE_STOCKOUT|DUAL|AMBIGUOUS)$")
    evidence_ref: str = ""


class AdvanceStatusRequest(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(acknowledged|executed|verified)$",
        description="Target status. Must be the next step in the lifecycle.",
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/feedback")
def get_feedback(warehouse_id: str | None = None):
    """
    Return all recommendation_log rows, ordered newest first.
    Each row includes a computed `failures_ceased` field
    (failures_before - failures_after) when both values are available.
    """
    return list_recommendations(warehouse_id=warehouse_id)


@router.post("/feedback", status_code=201)
def post_feedback(body: CreateRecommendationRequest):
    """
    Log a new recommendation derived from a diagnosis verdict.
    Captures `failures_before` from live pendency_mv at creation time
    so the closed-loop delta can be computed after the action is taken.
    """
    try:
        return create_recommendation(
            warehouse_id=body.warehouse_id,
            bin_label=body.bin,
            fsn=body.fsn,
            verdict=body.verdict,
            evidence_ref=body.evidence_ref,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/feedback/{rec_id}/status")
def patch_status(rec_id: int, body: AdvanceStatusRequest):
    """
    Advance a recommendation through its lifecycle:
      suggested → acknowledged → executed → verified

    On 'executed': captures failures_after from live pendency_mv and
    computes failures_ceased = failures_before - failures_after.
    On 'verified': sets resolved_at timestamp.
    """
    try:
        return advance_status(rec_id=rec_id, new_status=body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
