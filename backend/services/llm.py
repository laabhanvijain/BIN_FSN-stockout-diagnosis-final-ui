"""
backend/services/llm.py
========================
LLM client wrapper for Ollama via OpenAI-compatible API.

Uses a single model (default llama3.1:8b) with tool-calling support.
Simpler than the two-stage Anthropic approach, but requires more guardrails
for smaller models that may write SQL in prose or hallucinate findings.
"""

import logging
from openai import OpenAI
from backend.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Get or create the OpenAI client (Ollama-compatible)."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


def chat(messages: list[dict], tools: list[dict] | None = None):
    """
    Call the LLM with messages and optional tools.
    
    Args:
        messages: Chat messages in OpenAI format
        tools: Tool definitions in OpenAI format (optional)
    
    Returns:
        OpenAI ChatCompletion response
    """
    client = get_client()
    
    kwargs = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0,
    }
    
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as e:
        logger.exception("LLM call failed: %s", e)
        raise
