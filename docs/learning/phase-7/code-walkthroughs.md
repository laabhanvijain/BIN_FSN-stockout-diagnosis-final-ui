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

This file is the FastAPI router for the LLM assistant.

It exposes the backend endpoint that the frontend chat UI calls.

The route is:

```text
POST /api/ask
```

In FastAPI, this file does not become `/api/ask` all by itself. It defines `/ask`, and `backend/main.py` mounts all routers under the `/api` prefix.

So the local route in this file is:

```python
@router.post("/ask", response_model=AskResponse)
```

And the actual browser-facing route becomes:

```text
/api/ask
```

## What This File Is Responsible For

`ask.py` is responsible for the API boundary.

That means it handles:

- the incoming HTTP request
- request body validation
- response body shape
- error conversion into HTTP errors
- calling the real assistant logic in `agent.py`

It does not directly:

- call Ollama
- write prompts
- run SQL
- run nGQL
- decide verdicts
- synthesize final reasoning

Those jobs belong to service files such as `agent.py`, `llm.py`, `prompts.py`, and `guards.py`.

Correct mental model:

```text
ask.py = receptionist / API door
agent.py = investigator / reasoning engine
llm.py = phone line to Ollama
prompts.py = instructions for the assistant
guards.py = safety checker
```

## Imports

The file starts with:

```python
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.agent import ask
```

`logging` lets the backend record errors.

`APIRouter` lets this file define a group of API routes.

`HTTPException` lets the code return a proper HTTP error response, such as status code `503`.

`BaseModel` and `Field` come from Pydantic. They define and validate request/response shapes.

`ask` is imported from `backend.services.agent`. This is the real LLM assistant function.

## Router And Logger

```python
router = APIRouter()
logger = logging.getLogger(__name__)
```

`router` is where endpoints are registered.

`logger` is used when something fails, especially in `post_ask()`.

`__name__` means the logger name will match this Python module, which helps identify where logs came from.

## `AskRequest`

```python
class AskRequest(BaseModel):
    question: str
    warehouse_id: str
    depth_mode: str = "FAST"
```

This class describes the JSON body that the frontend must send.

Example request:

```json
{
  "question": "Why is BIN-PICKER-A failing?",
  "warehouse_id": "WH-BLR-001",
  "depth_mode": "FAST"
}
```

Field meanings:

`question` is the user's natural-language question.

`warehouse_id` scopes the investigation to one warehouse.

`depth_mode` controls how much time the assistant can spend.

Current modes:

```text
FAST = shorter budget, quick answer
THOROUGH = longer budget, deeper investigation
```

Important detail:

In the current model, `warehouse_id` is required by the backend because it is typed as `str` with no default.

However, `frontend/src/api.js` only sends `warehouse_id` if one exists:

```javascript
...(warehouseId && { warehouse_id: warehouseId })
```

So if the frontend ever calls `askQuestion()` without a warehouse ID, FastAPI will reject the request with a validation error.

That is worth remembering while debugging.

## `CitationItem`

```python
class CitationItem(BaseModel):
    id: str = Field(description="Citation reference (e.g. c1)")
    engine: str = Field(description="starrocks or nebulagraph")
    query: str = Field(description="SQL or nGQL executed")
    row_count: int
```

This defines what one citation looks like in the API response.

A citation is the proof behind an assistant claim.

Example citation:

```json
{
  "id": "c1",
  "engine": "starrocks",
  "query": "SELECT COUNT(DISTINCT picklist_item_fsn) ...",
  "row_count": 1
}
```

Notice that this response model does not expose full rows to the frontend.

`agent.py` internally stores `rows` inside citations, but `AskResponse` only returns:

```text
id, engine, query, row_count
```

This is one reason the current frontend citation display can drift, because `Assistant.jsx` expects older fields such as `rows` and `type`.

## `AskResponse`

```python
class AskResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    partial: bool = Field(description="True if answer is incomplete due to timeout")
    iterations: int = Field(description="Number of LLM tool loops")
    elapsed_ms: int = Field(description="Time taken in milliseconds")
```

This class describes what the backend sends back to the frontend.

Field meanings:

`answer` is the final natural-language answer shown to the user.

`citations` is the list of evidence sources used.

`partial` tells whether the answer may be incomplete because the assistant hit its time budget.

`iterations` tells how many LLM/tool-loop rounds happened.

`elapsed_ms` tells how long the assistant request took.

Example response:

```json
{
  "answer": "BIN-PICKER-A shows picker concentration... Recommended action: verify picker process.",
  "citations": [
    {
      "id": "c1",
      "engine": "starrocks",
      "query": "SELECT ...",
      "row_count": 1
    }
  ],
  "partial": false,
  "iterations": 3,
  "elapsed_ms": 4210
}
```

## `post_ask(req: AskRequest)`

This is the main endpoint.

```python
@router.post("/ask", response_model=AskResponse)
def post_ask(req: AskRequest):
```

When a user sends a chat question, FastAPI:

1. Receives the HTTP request.
2. Parses the JSON body.
3. Validates it against `AskRequest`.
4. Calls `post_ask(req)`.
5. Validates the returned object against `AskResponse`.
6. Sends JSON back to the frontend.

Inside the endpoint:

```python
result = ask(req.question, req.warehouse_id, req.depth_mode)
```

This is the handoff from router to service layer.

The router says:

```text
I received a valid API request. Agent, please investigate this question.
```

Then `agent.py` handles the actual reasoning.

## Why It Wraps The Result In `AskResponse`

The agent returns a plain Python dictionary.

The router converts it into a typed response:

```python
return AskResponse(
    answer=result["answer"],
    citations=[CitationItem(**c) for c in result["citations"]],
    partial=result.get("partial", False),
    iterations=result.get("iterations", 0),
    elapsed_ms=result.get("elapsed_ms", 0),
)
```

This has two benefits.

First, FastAPI gets a clean predictable response shape.

Second, if the agent returns extra internal data, the API does not automatically expose all of it.

For example, `agent.py` citations may include `rows`, but `CitationItem` does not define `rows`, so the response model only exposes the allowed citation fields.

## Error Handling

The endpoint catches unexpected exceptions:

```python
except Exception:
    logger.exception("POST /ask failed")
    raise HTTPException(
        detail="LLM assistant not available. Check Ollama is running and LLM_BASE_URL is configured.",
        status_code=503,
    )
```

This means if the assistant fails badly, the API returns:

```text
503 Service Unavailable
```

A `503` means:

```text
The server exists, but this service is temporarily unavailable.
```

That is appropriate for cases like:

- Ollama is not running.
- LLM config is wrong.
- agent call crashes unexpectedly.

Small caveat:

This catches all exceptions and returns the same message. That is simple for users, but in production we may want more specific errors for validation, model timeout, database failure, and graph failure.

## `GET /ask/available`

```python
@router.get("/ask/available")
def get_ask_available():
```

This is a small health-check endpoint.

Its job is to answer:

```text
Is the assistant configured enough to be available?
```

It tries to create the LLM client:

```python
from backend.services.llm import get_client
client = get_client()
return True
```

If anything fails, it returns `False`.

Important caveat:

This function creates the client, but it does not actually send a test message to Ollama.

So it mostly checks whether client construction works, not whether the model is fully reachable and healthy.

A stronger production health check would make a tiny request to the LLM or call the Ollama model list endpoint.

## Full Request Flow Through This File

Example user question:

```text
Why is BIN-PICKER-A failing?
```

Flow:

```text
Assistant.jsx
-> api.js askQuestion()
-> POST /api/ask
-> ask.py validates AskRequest
-> post_ask() calls agent.ask()
-> agent.py runs LLM/tool loop
-> ask.py shapes result into AskResponse
-> frontend receives answer/citations/metadata
```

## What To Remember

`ask.py` is thin by design.

A good router should mostly handle HTTP concerns and delegate business logic to services.

In this project:

```text
ask.py should stay small.
agent.py is allowed to be complex.
```

That separation keeps the API layer easier to understand and test.
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

