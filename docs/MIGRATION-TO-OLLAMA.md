# Migration to Ollama - Summary

**Date**: June 29, 2026  
**Status**: Complete

---

## Overview

Migrated the BIN-FSN Stockout Diagnosis system from **Anthropic Claude (Haiku + Sonnet two-stage)** to **Ollama (single-model llama3.1:8b)** with architectural changes to support weaker local models.

---

## Key Changes

### 1. **LLM Architecture**

**Before** (Anthropic):
- Two-stage: Haiku 4.5 (routing) → Sonnet 4.5 (reasoning)
- Cloud API, pay-per-token
- High reliability, minimal fallback logic needed

**After** (Ollama):
- Single-model: llama3.1:8b (or any Ollama model)
- Local inference, zero cost
- OpenAI-compatible API
- Extensive deterministic fallbacks for weaker models

### 2. **Graph Signals Strategy**

**Before**:
- Pre-computed for every diagnosis row
- Enriched in `backend/services/graph.py::enrich_signals()`
- Returned with `/api/diagnoses` response
- Fast UX (immediate display)

**After**:
- Queried dynamically by LLM agent on-demand
- Agent decides which signals to query based on question
- More flexible (arbitrary graph traversals possible)
- Slightly slower (wait for LLM to query)

### 3. **Agent Implementation**

**Before** (`backend/services/llm.py`):
- Clean two-stage flow
- ~300 lines
- Trust Sonnet to use tools correctly

**After** (`backend/services/agent.py`):
- Comprehensive tool loop with fallbacks
- ~600 lines
- Handles:
  - SQL-in-prose extraction
  - Hallucination detection
  - Auto-bootstrap for common questions
  - Incomplete answer synthesis
  - AMBIGUOUS investigation checklist

### 4. **New Components**

Created:
- `backend/services/agent.py` - main LLM agent with tool loop
- `backend/services/guards.py` - SQL/nGQL validation
- `backend/services/prompts.py` - system prompts and AMBIGUOUS playbook
- `data/data_generator.py` - continuous event generator

Modified:
- `backend/services/llm.py` - simple Ollama client wrapper
- `backend/services/diagnosis.py` - removed graph signal pre-computation
- `backend/services/graph.py` - kept helper functions, removed enrich_signals()
- `backend/routers/ask.py` - updated for new agent API
- `backend/config.py` - added Ollama settings

---

## Configuration Changes

### Environment Variables

**Removed**:
- `ANTHROPIC_API_KEY`

**Added**:
- `LLM_BASE_URL=http://localhost:11434/v1`
- `LLM_API_KEY=ollama`
- `LLM_MODEL=llama3.1:8b`
- `ASK_TOTAL_TIMEOUT_MS=10000`
- `ASK_THOROUGH_TIMEOUT_MS=30000`
- `ASK_MAX_ITERATIONS=12`
- `ASK_PER_QUERY_TIMEOUT_MS=5000`

### Dependencies

**Changed** (`backend/requirements.txt`):
- Removed: `anthropic==0.28.0`
- Added: `openai==1.30.0`

---

## API Changes

### POST /api/ask

**Before**:
```json
{
  "question": str,
  "warehouse_id": str,
  "window_days": int
}
```

Response included `route_tag` (Haiku's routing decision).

**After**:
```json
{
  "question": str,
  "warehouse_id": str,
  "depth_mode": "FAST" | "THOROUGH"
}
```

Response includes:
- `partial`: bool (timeout indicator)
- `iterations`: int (tool loop count)
- `elapsed_ms`: int (performance metric)

---

## Depth Modes

Two investigation budgets:

- **FAST** (10s): Quick verdict + one upstream check
- **THOROUGH** (30s): Complete AMBIGUOUS investigation

---

## Deterministic Fallbacks

Agent includes these helpers for weaker models:

1. **Auto-bootstrap**: Detects FSN+BIN in question → runs verdict SQL automatically
2. **SQL extraction**: Model pastes SQL in prose → extract and execute
3. **Hallucination blocking**: Model claims findings without queries → nudge to use tools
4. **Graph auto-trace**: Known graph patterns → run canned nGQL
5. **AMBIGUOUS completion**: Investigation incomplete → auto-run missing checks
6. **Answer synthesis**: Timeout or incomplete → build answer from citations

---

## Data Generator

New continuous generator (`data/data_generator.py`):

**Event rotation**:
```
repeat → repeat → inventory_adjust → new_bin → new_fsn
```

**Usage**:
```bash
python data/data_generator.py              # Continuous
python data/data_generator.py --once       # Single batch
python data/data_generator.py --interval 5 # Custom interval
```

State tracked in `.data_generator_state.json`.

---

## Prerequisites

**New requirement**: Ollama must be installed and running

```bash
# Install Ollama (https://ollama.com)
ollama pull llama3.1:8b
ollama serve
```

---

## Migration Checklist

- [x] Remove anthropic dependency, add openai
- [x] Rewrite llm.py for Ollama
- [x] Create agent.py with tool loop + fallbacks
- [x] Create guards.py for validation
- [x] Create prompts.py for system prompts
- [x] Update diagnosis.py (remove pre-computation)
- [x] Update graph.py (keep helpers only)
- [x] Update ask.py router
- [x] Create data_generator.py
- [x] Update config.py
- [x] Update .env.example
- [x] Update README.md
- [x] Update CLAUDE.md
- [x] Update design/design-doc.md
- [x] Document migration

---

## Performance Comparison

| Aspect | Anthropic | Ollama |
|--------|-----------|--------|
| **Cost** | $0.25-$1.50 per 100 questions | $0 (local) |
| **Latency** | 2-5s typical | 3-8s typical |
| **Reliability** | Very high (Sonnet) | Medium (needs fallbacks) |
| **Privacy** | Cloud API | Fully local |
| **Tool calling** | Native, excellent | Good with fallbacks |
| **Citation quality** | Excellent | Good |

---

## Known Limitations

1. **Weaker reasoning**: llama3.1:8b less reliable than Claude Sonnet for complex multi-step logic
2. **Slower**: Local inference slower than cloud API (but no network latency)
3. **More defensive code**: 600-line agent.py vs 300-line llm.py
4. **Model dependency**: Must have Ollama running (one more service to manage)

---

## Upgrade Path

To use a stronger model:

1. Pull the model:
   ```bash
   ollama pull codellama:13b
   # or
   ollama pull mixtral:8x7b
   ```

2. Update `.env`:
   ```bash
   LLM_MODEL=codellama:13b
   ```

3. Restart backend

Stronger models → less reliance on deterministic fallbacks.

---

## Rollback

To revert to Anthropic:

1. Checkout commit before migration
2. Or:
   - Restore old `backend/services/llm.py`
   - Restore old `backend/routers/ask.py`
   - Restore `backend/requirements.txt`
   - Remove agent.py, guards.py, prompts.py
   - Update config.py and .env.example

---

## Testing

Smoke test updated to work with Ollama:

```bash
bash infra/smoke_test.sh
```

Checks:
- StarRocks connectivity
- NebulaGraph connectivity
- Ollama availability
- Verdict SQL
- LLM assistant (if Ollama running)

---

## Credits

Architecture inspired by Ankit Pradhan's FSN-BIN-diagnosis POC, adapted for this project's structure and conventions.
