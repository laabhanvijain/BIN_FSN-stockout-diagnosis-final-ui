# LLD 07 · LLM Agent

> Status: **DONE** (M7 · 2026-06-26). Source: `backend/services/llm.py`, `backend/routers/ask.py`.

---

## Two-stage architecture

```
User question
    │
    ▼
Stage 1 — Claude Haiku 4.5 (routing)
    │   Classifies question into: SQL_ONLY | GRAPH_ONLY | SQL_GRAPH | OUT_OF_SCOPE
    │   ~1 call, max_tokens=10, very fast and cheap
    ▼
Stage 2 — Claude Sonnet 4.5 (reasoning)
    │   Agentic tool loop (max 8 rounds):
    │     run_sql(query)  → executes on StarRocks, returns up to 50 rows
    │     run_ngql(query) → executes on NebulaGraph, returns up to 50 rows
    │   Assembles answer with mandatory CITATIONS block
    ▼
Response: { answer, citations[], route_tag }
```

---

## Security guardrails

| Layer | Implementation |
|-------|---------------|
| SQL whitelist | Regex blocks INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/CREATE — returns error string to model (not user) |
| nGQL whitelist | Regex blocks INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/REBUILD |
| Row cap | `fetchmany(50)` on SQL; `rows[:50]` on nGQL — keeps context size bounded |
| Tool rounds cap | Max 8 tool-call rounds — prevents runaway loops; returns partial result with warning |
| API key gate | `/ask` returns 503 if `ANTHROPIC_API_KEY` is empty — no silent failure |

---

## Citation enforcement

The system prompt mandates:
```
You MUST end your response with a CITATIONS block:
---CITATIONS---
[1] SQL: <query> → <finding>
[2] GRAPH: <nGQL> → <finding>
```

Post-processing checks for `---CITATIONS---` in the answer. If absent, a ⚠️ warning
is appended so the UI can visually flag uncited answers.

---

## Tool routing optimisation

Haiku's routing tag restricts which tools Sonnet receives:
- `SQL_ONLY` → only `run_sql` offered → no unnecessary nGQL calls
- `GRAPH_ONLY` → only `run_ngql` offered
- `SQL_GRAPH` → both tools offered
- `OUT_OF_SCOPE` → Sonnet skipped entirely → returns canned response

---

## API contract

```
POST /api/ask
Body: { "question": string (3–500 chars), "warehouse_id": string? }

Response:
{
  "answer": "...",
  "route_tag": "SQL_GRAPH",
  "citations": [
    { "type": "sql",  "query": "SELECT ...", "rows": [...], "error": null },
    { "type": "ngql", "query": "MATCH ...", "rows": [...], "error": null }
  ]
}
```

503 is returned if `ANTHROPIC_API_KEY` is not set.
422 is returned if `question` is empty or > 500 chars (FastAPI validation).

---

## Key Technical Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| Haiku for routing | Cheap, fast model | Ask Sonnet everything | Routing is a classification task; Haiku is 10x cheaper and sufficient |
| Sonnet for reasoning | Capable tool-use model | Haiku for everything | Complex multi-hop diagnosis needs stronger reasoning |
| Max 8 tool rounds | Hard cap | Unlimited | Stay under 10s SLA; prevents runaway loops |
| Regex query whitelist | Regex on keywords | ORM / prepared statements | LLM generates free-text SQL; we must sanitise before execution |
| Error string to model (not user) | Return `{"error": "BLOCKED..."}` to model | Raise HTTP 400 | Model can rephrase the query; user sees the final answer, not raw errors |
| Row cap at 50 | `fetchmany(50)` | No cap | Keeps prompt context bounded; prevents token overflow |
| Citation enforcement via post-process | Check for `---CITATIONS---` | Trust model to always cite | Defense-in-depth; model occasionally forgets — we flag rather than silently serve |
