"""
backend/routers/ask.py
======================
POST /api/ask — LLM assistant endpoint.

Single-model architecture (Ollama):
  - Uses llama3.1:8b (or configured model) with tool-calling
  - Supports depth_mode: FAST (10s) or THOROUGH (30s)
  - Deterministic fallbacks for weaker models (auto-bootstrap, SQL extraction)
  - Mandatory citation enforcement
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.agent import ask

router = APIRouter()
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str
    warehouse_id: str
    depth_mode: str = "FAST"  # FAST or THOROUGH


class CitationItem(BaseModel):
    id: str = Field(description="Citation reference (e.g. c1)")
    engine: str = Field(description="starrocks or nebulagraph")
    query: str = Field(description="SQL or nGQL executed")
    row_count: int


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    partial: bool = Field(description="True if answer is incomplete due to timeout")
    iterations: int = Field(description="Number of LLM tool loops")
    elapsed_ms: int = Field(description="Time taken in milliseconds")


@router.post("/ask", response_model=AskResponse)
def post_ask(req: AskRequest):
    """
    Ask the LLM assistant a question over live warehouse data.
    
    depth_mode:
        FAST: 10s budget, quick answers
        THOROUGH: 30s budget, deeper investigation
    
    Returns answer with citations and performance metrics.
    """
    try:
        result = ask(req.question, req.warehouse_id, req.depth_mode)
        return AskResponse(
            answer=result["answer"],
            citations=[CitationItem(**c) for c in result["citations"]],
            partial=result.get("partial", False),
            iterations=result.get("iterations", 0),
            elapsed_ms=result.get("elapsed_ms", 0),
        )
    except Exception:
        logger.exception("POST /ask failed")
        raise HTTPException(
            detail="LLM assistant not available. Check Ollama is running and LLM_BASE_URL is configured.",
            status_code=503,
        )


@router.get("/ask/available")
def get_ask_available():
    """Health check: is the LLM assistant configured?"""
    from backend.config import settings
    try:
        # Try to connect to Ollama
        from backend.services.llm import get_client
        client = get_client()
        return True
    except Exception:
        return False
