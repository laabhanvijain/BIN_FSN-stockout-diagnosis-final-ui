# backend/services/llm.py + backend/routers/ask.py — Code Walkthrough

> Source: `backend/services/llm.py`, `backend/routers/ask.py`
> Milestone: M7 · Last updated: 2026-06-26

## What it does

Implements a two-stage LLM pipeline: Haiku classifies the question cheaply,
then Sonnet reasons with live SQL and graph data through a tool-calling loop,
producing a cited natural-language answer.

---

## File structure

```
backend/
├── services/
│   └── llm.py      ← routing, tool executors, Haiku call, Sonnet loop, citation check
└── routers/
    └── ask.py      ← POST /api/ask, request/response models, API-key gate
```

---

## Stage 1: Haiku routing (`_route`)

```python
resp = _client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=10,
    system=_HAIKU_SYSTEM,
    messages=[{"role": "user", "content": question}],
)
tag = resp.content[0].text.strip().upper()
# returns: SQL_ONLY | GRAPH_ONLY | SQL_GRAPH | OUT_OF_SCOPE
```

Haiku sees only the question and returns a single tag. `max_tokens=10` ensures
it can only return the tag — nothing else. This costs ~0.01¢ and takes < 1s.

The tag is used to restrict which tools Sonnet receives:
- `SQL_ONLY` → only `run_sql` in the tools list → no wasted nGQL calls
- `OUT_OF_SCOPE` → Sonnet is skipped entirely → instant canned response

---

## Stage 2: Sonnet reasoning loop (`_reason`)

```python
for _ in range(8):   # hard cap: max 8 tool-call rounds
    resp = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=_SONNET_SYSTEM,
        tools=tools,         # filtered by route_tag
        messages=messages,
    )

    tool_results = []
    for block in resp.content:
        if block.type == "tool_use":
            result = _run_sql(block.input["query"])  # or _run_ngql
            citations.append({...})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, ...})

    if tool_results:
        # Feed results back → Sonnet continues reasoning
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": tool_results})
        continue

    # No tool calls → Sonnet is done → extract answer
    answer = "".join(block.text for block in resp.content if hasattr(block, "text"))
    break
```

The loop continues as long as Sonnet makes tool calls. Each round: Sonnet
decides what to query → we execute it → return results → Sonnet processes them
→ decides next query or final answer.

---

## Security: query whitelist

```python
_SQL_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|...)\b", re.IGNORECASE
)

def _validate_sql(query: str) -> str | None:
    if _SQL_FORBIDDEN.search(query):
        return "BLOCKED: only SELECT/WITH queries are allowed."
    return None
```

The error string is returned to the **model** (not the user) as a `tool_result`.
Sonnet can then rephrase and try again. This means:
1. The user sees a clean final answer.
2. Sonnet gets feedback and can self-correct.
3. No DML ever reaches StarRocks or NebulaGraph.

---

## Citation enforcement

```python
if "---CITATIONS---" not in answer:
    answer += "\n\n⚠️ [System: citation block missing — claims may not be verified]"
```

The system prompt mandates the block. Post-processing is a defence layer —
if Sonnet forgets, the UI gets a visible warning badge rather than silently
serving an uncited answer.

---

## `backend/routers/ask.py`

```python
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    warehouse_id: str | None = None

@router.post("/ask", response_model=AskResponse)
def ask_endpoint(body: AskRequest):
    if not settings_ok():
        raise HTTPException(503, "LLM not configured")
    result = ask(question=body.question, warehouse_id=body.warehouse_id)
    return AskResponse(...)
```

- Pydantic validates `question` length (3–500 chars) before any LLM call.
- `settings_ok()` checks for `ANTHROPIC_API_KEY` — returns 503 rather than
  letting the call fail deep inside the Anthropic client.
- `response_model=AskResponse` auto-validates the outgoing shape.

---

## Example interaction

**Question**: "Why is BIN-PICKER-A failing so often?"

**Haiku routes**: `SQL_ONLY` (picker stats are in pendency_mv)

**Sonnet round 1**:
```sql
SELECT picklist_assigned_to, COUNT(*) as failures
FROM pendency_mv
WHERE picklist_source_location_label = 'BIN-PICKER-A'
  AND irt_ticket_id IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC
```
→ rows: `[{"picklist_assigned_to": "PKR-BAD", "failures": 8}]`

**Sonnet final answer**:
"BIN-PICKER-A has 8 INF failures, all attributed to picker PKR-BAD (100% concentration).
This strongly suggests a picker-error root cause rather than phantom inventory."

```
---CITATIONS---
[1] SQL: SELECT picklist_assigned_to... → PKR-BAD: 8 failures (100%)
```

---

## Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Two-stage (Haiku + Sonnet) | Separate models | Haiku routes cheaply; Sonnet reasons powerfully. Eliminates Sonnet call for trivial/OOS questions |
| Max 8 tool rounds | Hard cap | Prevents runaway loops; keeps latency under 10s SLA |
| Whitelist via regex on keywords | Keyword deny-list | LLM generates free-text SQL — must sanitise before execution; keyword blocking covers all DML/DDL |
| Error to model, not user | `tool_result` with error | Model self-corrects; user sees clean answer |
| Row cap at 50 | `fetchmany(50)` | Bounded context size; prevents token overflow on large tables |
| Citation enforcement post-process | Check + warning append | Defense-in-depth; model forgets occasionally; UI can badge uncited answers |
| 503 on missing API key | HTTPException(503) | Explicit failure over silent broken response |
