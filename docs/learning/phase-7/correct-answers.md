# Phase 7 Correct Answers

## 1. Which endpoint handles assistant questions?

Assistant questions are handled by:

```text
POST /api/ask
```

The FastAPI router is `backend/routers/ask.py`.

The route function is `post_ask()`.

It calls the main agent function:

```python
ask(req.question, req.warehouse_id, req.depth_mode)
```

## 2. Why does the assistant need tools?

The assistant needs tools because the LLM does not directly know the live warehouse data.

It needs `query_starrocks` to fetch SQL/count data.

It needs `query_nebulagraph` to fetch relationship/context data.

Without tools, the LLM would be guessing from its general language knowledge.

## 3. What does `guards.py` protect against?

`guards.py` protects the databases from unsafe LLM-generated queries.

It blocks mutation or destructive operations such as:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
```

It also forces SQL queries to be read-only and warehouse-scoped.

This matters because LLM output should not be trusted blindly.

## 4. Why are citations required?

Citations are required so every factual claim can be traced back to real query results.

They reduce hallucination risk and make the assistant's answer auditable.

For example, the assistant should not simply say:

```text
This FSN failed across many BINs.
```

It should say that based on a cited query result:

```text
This FSN failed across 3 distinct BINs [c1].
```

## 5. Why is Ollama used through an OpenAI-compatible API?

Ollama exposes an OpenAI-compatible API.

That lets the backend use the standard OpenAI Python client while still running a local model.

This keeps integration simple and familiar.

It also makes it easier to switch between compatible providers later.

## 6. What is the difference between FAST and THOROUGH mode?

FAST mode has a shorter time budget, around 10 seconds.

It is meant for quick operational answers.

THOROUGH mode has a longer time budget, around 30 seconds.

It is meant for deeper investigation, especially when the case is ambiguous or needs more tool calls.

## 7. What frontend/backend mismatch did we notice in citations?

The current backend returns citation fields like:

```text
id
engine
query
row_count
```

But `Assistant.jsx` expects older fields like:

```text
type
rows
```

Specifically, frontend code uses:

```javascript
c.type
c.rows.length
```

This may break because those fields may not exist in the current backend response.

The frontend also still expects `route_tag`, but the current backend no longer returns it.

## 8. What is tool calling in this project?

Tool calling means the LLM can ask the backend to run a specific function.

In this project, the two main tools are:

```text
query_starrocks
query_nebulagraph
```

The LLM chooses a tool, the backend executes it, and the result is returned to the LLM for reasoning.

## 9. What is auto-bootstrap?

Auto-bootstrap is a deterministic helper in `agent.py`.

If the user's question contains both an FSN and a BIN, the backend automatically runs important StarRocks queries before relying on the LLM.

This helps the assistant start with real evidence and reduces the chance of a weak local model failing to query the right data.

## 10. Why does the backend synthesize answers sometimes?

The backend synthesizes answers when the LLM times out or gives an incomplete answer.

Instead of returning nothing, it uses the citations already collected to build a basic answer.

This improves reliability and gives the user something useful even when the model does not complete perfectly.
