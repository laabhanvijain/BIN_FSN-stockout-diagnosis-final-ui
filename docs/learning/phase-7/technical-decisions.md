# Phase 7 Technical Decisions

## Decision 1: Use A Tool-Grounded Assistant

The assistant should not answer from memory.

It should use tools to query live warehouse data.

Tools available:

```text
query_starrocks
query_nebulagraph
```

This makes the assistant more reliable because factual claims can be tied to query results.

## Decision 2: Use Ollama Locally

The current implementation uses Ollama with `llama3.1:8b` by default.

Benefits:

- Runs locally.
- No per-token cloud cost.
- Better privacy for warehouse data.
- Easy to swap local models.

Trade-offs:

- Local model may be weaker than cloud frontier models.
- More fallback code is needed.
- Ollama must be installed and running.

## Decision 3: Use OpenAI-Compatible Client For Ollama

The backend uses the OpenAI Python client against Ollama's OpenAI-compatible API.

This keeps the code familiar and reduces custom integration work.

Configuration:

```text
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1:8b
```

## Decision 4: Single-Model Tool Loop Instead Of Old Two-Stage Routing

Older design:

```text
Claude Haiku routes question
Claude Sonnet reasons
```

Current design:

```text
One Ollama model handles tool calling and answering
```

Why this changed:

- Removes cloud dependency.
- Simplifies provider setup.
- Supports local inference.

Trade-off:

The backend needs more deterministic fallbacks because the smaller local model may make more mistakes.

## Decision 5: Add Defensive Fallbacks

`agent.py` includes fallback logic for weaker model behavior.

Examples:

- Recover JSON tool calls written as text.
- Extract SQL from prose and execute it.
- Block hallucinated answers without citations.
- Auto-bootstrap basic verdict queries when FSN and BIN are present.
- Synthesize an answer from citations if the model times out.

This is practical engineering.

The backend does not fully trust the model to behave perfectly.

## Decision 6: Validate All LLM-Generated Queries

`guards.py` validates SQL and nGQL before execution.

This is necessary because LLM-generated text can be wrong or unsafe.

SQL must be read-only and warehouse-scoped.

nGQL must be read-only.

This prevents dangerous operations such as:

```text
DROP
DELETE
UPDATE
INSERT
ALTER
CREATE
```

## Decision 7: Use Citations

Every successful tool result becomes a citation.

Citations are important because they make answers auditable.

Without citations, the user cannot know whether the assistant is using real data or guessing.

## Decision 8: Use Row Caps

Tool results are capped at 50 rows.

Why:

- Prevents huge responses.
- Keeps LLM context manageable.
- Reduces latency.
- Makes citations easier to inspect.

Improvement for production:

Make the cap configurable and include a `truncated` flag when more rows existed than were returned.

## Decision 9: Use FAST And THOROUGH Modes

The assistant supports two depth modes.

```text
FAST = 10 second budget
THOROUGH = 30 second budget
```

FAST is for quick operational answers.

THOROUGH is for deeper investigation, especially ambiguous cases.

## Decision 10: Return Performance Metadata

Current backend response includes:

```text
partial
iterations
elapsed_ms
```

These fields help diagnose assistant behavior.

- `partial`: answer may be incomplete due to timeout.
- `iterations`: how many LLM/tool loop rounds happened.
- `elapsed_ms`: how long the request took.

## Decision 11: Fix Frontend/Backend Drift Soon

Current backend no longer returns `route_tag`, but frontend still reads it.

Current backend citations use `engine` and `row_count`, while frontend expects `type` and `rows.length`.

This mismatch should be fixed because citation display may break.

Recommended fix:

- Update `Assistant.jsx` to use `c.engine` instead of `c.type`.
- Use `c.row_count` instead of `c.rows.length`.
- Remove or replace `route_tag` display.
- Optionally show `partial`, `iterations`, and `elapsed_ms` in the UI.

## Decision 12: Treat Older LLM Docs As Stale

`backend-ask-llm.md` still describes the old Claude Haiku/Sonnet design.

Current code uses Ollama and `agent.py`.

The migration doc is more accurate for current behavior.
