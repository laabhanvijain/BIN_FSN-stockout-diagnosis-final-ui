# Phase 7 Code Walkthrough: LLM Assistant

Files read for this phase:

- `backend/routers/ask.py`
- `backend/services/agent.py`
- `backend/services/llm.py`
- `backend/services/prompts.py`
- `backend/services/guards.py`
- `frontend/src/Assistant.jsx`
- `frontend/src/api.js`
- `docs/code-walkthroughs/backend-ask-llm.md`
- `docs/MIGRATION-TO-OLLAMA.md`

## Big Picture

Phase 7 adds a chat assistant.

The assistant lets a user ask a question in normal language, then the backend investigates using tools.

High-level runtime flow:

```text
User types question
-> Assistant.jsx sends POST /api/ask
-> ask.py receives request
-> agent.py runs LLM tool loop
-> StarRocks and/or NebulaGraph are queried
-> citations are collected
-> final answer returns to frontend
```

## `backend/routers/ask.py`

This file defines the HTTP endpoint:

```python
@router.post("/ask", response_model=AskResponse)
def post_ask(req: AskRequest):
```

The request model is:

```python
class AskRequest(BaseModel):
    question: str
    warehouse_id: str
    depth_mode: str = "FAST"
```

The response model is:

```python
class AskResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    partial: bool
    iterations: int
    elapsed_ms: int
```

So `ask.py` is the HTTP wrapper.

It does not do the actual reasoning.

It calls:

```python
result = ask(req.question, req.warehouse_id, req.depth_mode)
```

That `ask()` function comes from `backend/services/agent.py`.

## `backend/services/llm.py`

This file creates the LLM client.

Important code:

```python
_client = OpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)
```

Even though the client is named `OpenAI`, the backend is usually talking to local Ollama.

Default settings:

```text
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1:8b
```

The `chat()` function sends messages to the model:

```python
client.chat.completions.create(**kwargs)
```

If tools are passed, it also sends:

```python
kwargs["tools"] = tools
kwargs["tool_choice"] = "auto"
```

That allows the model to call tools when needed.

## `backend/services/prompts.py`

This file builds the system prompt.

The system prompt tells the assistant:

- warehouse context
- verdict definitions
- available tools
- graph signal examples
- critical rules
- answer format

The verdict rules in the prompt are:

```text
PHANTOM_INVENTORY = >=3 distinct FSNs failing in one BIN
GENUINE_STOCKOUT = >=2 distinct BINs failing for one FSN
DUAL = both thresholds met
AMBIGUOUS = neither threshold met
```

The prompt also says:

```text
ALWAYS cite every factual claim.
NEVER answer from memory.
End EVERY answer with Recommended action.
```

This is important because the LLM's behavior is strongly shaped by the system prompt.

## `backend/services/guards.py`

This file protects the databases from unsafe LLM-generated queries.

`validate_sql(sql, warehouse_id)` checks:

1. SQL is not empty.
2. SQL does not contain forbidden mutation keywords.
3. SQL starts with `SELECT` or `WITH`.
4. SQL includes the current warehouse ID, unless it is a system-table query.

Forbidden SQL examples:

```text
INSERT
UPDATE
DELETE
DROP
TRUNCATE
ALTER
CREATE
REPLACE
MERGE
CALL
EXEC
```

`validate_ngql(ngql)` checks:

1. nGQL is not empty.
2. nGQL does not contain forbidden mutation keywords.
3. nGQL starts with an allowed read operation.

Allowed nGQL starts include:

```text
MATCH
GO
FETCH
LOOKUP
GET
SHOW
FIND
```

Guardrails are necessary because LLM output is generated text and should not be trusted blindly.

## `backend/services/agent.py`

This is the main Phase 7 file.

It defines two tools:

```python
query_starrocks
query_nebulagraph
```

These are stored in `TOOL_SPECS` in OpenAI function-calling format.

### `_execute_starrocks()`

This function:

1. Validates SQL with `guards.validate_sql()`.
2. Opens a StarRocks connection.
3. Executes the query.
4. Fetches rows.
5. Caps rows at 50.
6. Returns a dictionary result.

Returned shape:

```python
{
    "ok": True,
    "engine": "starrocks",
    "query": sql,
    "row_count": len(rows),
    "rows": rows,
}
```

### `_execute_nebulagraph()`

This function:

1. Validates nGQL with `guards.validate_ngql()`.
2. Opens a NebulaGraph session.
3. Prepends `USE <nebula_space>;`.
4. Executes the query.
5. Converts graph rows into dictionaries.
6. Caps rows at 50.
7. Returns a dictionary result.

Returned shape:

```python
{
    "ok": True,
    "engine": "nebulagraph",
    "query": ngql,
    "row_count": len(rows),
    "rows": rows,
}
```

### `execute_tool()`

This function routes a tool name to the right executor.

```python
if tool_name == "query_starrocks":
    return _execute_starrocks(...)
elif tool_name == "query_nebulagraph":
    return _execute_nebulagraph(...)
```

### Tool Parsing Helpers

Some local models may not use tool calling perfectly.

They may write JSON in the message text instead of making a real tool call.

So `agent.py` includes helpers to recover tool calls from text:

- `_extract_json_objects()`
- `_parse_text_tool_calls()`
- `_normalize_tool_calls()`

These are defensive helpers for weaker local models.

### Pattern Helpers

The agent extracts FSN and BIN from the question using regexes:

```python
_FSN_RE = re.compile(r"FSN-[A-Z0-9]+", re.I)
_BIN_RE = re.compile(r"\bbin\s+([A-Z][\w-]+)", re.I)
```

This supports auto-bootstrap.

### `_auto_bootstrap_verdict()`

If the user question contains both FSN and BIN, the backend automatically runs basic StarRocks queries.

It queries:

1. Distinct FSNs in that BIN.
2. Distinct BINs for that FSN.
3. Inventory item state.

This makes the answer more grounded even if the local model is slow to call tools.

### `_run_tool()`

This executes a tool call and adds successful results to citations.

Citation shape:

```python
{
    "id": "c1",
    "engine": "starrocks",
    "query": "SELECT ...",
    "row_count": 3,
    "rows": [...],
}
```

The tool result is also appended back into the model conversation.

That lets the LLM see the query result and continue reasoning.

### `_synthesize_answer()`

If the model times out or gives an incomplete answer, this function builds a basic answer from citations.

It can extract:

- distinct FSN count
- distinct BIN count
- verdict
- basic inventory details
- recommended action

This gives the user a useful fallback answer.

### `ask()`

This is the main entry point.

Flow:

```text
Start timer
Build system prompt
Add user question
Create citations list
Maybe auto-bootstrap SQL
Loop up to ask_max_iterations:
    call LLM
    extract tool calls
    if tool calls exist:
        run tools
        append results
        continue
    else:
        clean and return answer
If loop times out:
    synthesize answer from citations
```

This is why `agent.py` is long. It is a controlled investigation loop, not just a single LLM call.

## `frontend/src/api.js`

This file centralizes frontend API calls.

For the assistant:

```javascript
export const askQuestion = (question, warehouseId) =>
  http.post('/ask', {
    question,
    ...(warehouseId && { warehouse_id: warehouseId }),
  }).then(r => r.data)
```

So the frontend sends `POST /api/ask`.

## `frontend/src/Assistant.jsx`

This is the chat UI.

It stores:

```javascript
messages
input
loading
```

When the user clicks Send:

```javascript
const res = await askQuestion(q, warehouseId)
```

Then it appends the assistant response to the chat history.

It also has a `CitationBlock` component to show citations.

## Important Current Drift

There is a mismatch between current backend and current frontend/docs.

Current backend returns citations like:

```json
{
  "id": "c1",
  "engine": "starrocks",
  "query": "SELECT ...",
  "row_count": 3
}
```

But `Assistant.jsx` expects older fields:

```javascript
c.type
c.rows.length
```

This can break citation display because `type` and `rows` may be missing.

Also `Assistant.jsx` still expects:

```javascript
res.route_tag
```

But current backend no longer returns `route_tag`.

That field belonged to the older Claude Haiku/Sonnet routing design.

Correct current understanding:

```text
Backend = Ollama single-model agent with partial/iterations/elapsed_ms
Some frontend/docs = still Claude-era route_tag/citation assumptions
```

## Stale Walkthrough Doc

`docs/code-walkthroughs/backend-ask-llm.md` describes the older Claude architecture:

```text
Haiku routes question
Sonnet reasons with tools
route_tag returned
```

The current code uses:

```text
Ollama single-model tool loop in agent.py
```

So when studying Phase 7, trust the current code and `docs/MIGRATION-TO-OLLAMA.md` more than the old walkthrough.
