# Phase 7 Prerequisites: LLM Assistant

Phase 7 is where the project becomes an interactive assistant instead of only a dashboard.

Before this phase, the system can show deterministic diagnosis rows such as:

```text
BIN-X + FSN-Y -> PHANTOM_INVENTORY / GENUINE_STOCKOUT / DUAL / AMBIGUOUS
```

After this phase, the user can ask natural-language questions such as:

```text
Why is BIN-PICKER-A failing?
What should I do for FSN-S2-001?
Is this phantom inventory or genuine stockout?
```

The assistant then uses the backend, StarRocks, NebulaGraph, and an LLM to produce a cited answer.

## LLM

LLM means Large Language Model.

Examples:

- ChatGPT
- Claude
- Llama
- Mistral

In this project, the LLM is usually:

```text
Ollama running llama3.1:8b locally
```

The LLM does not store warehouse data.

Its job is to reason over warehouse data fetched by backend tools.

Correct mental model:

```text
The LLM should not guess.
The LLM should query tools, read results, then answer.
```

## Prompt

A prompt is the instruction given to the LLM.

In this project, the system prompt tells the LLM:

- You are a warehouse operations analyst.
- INF means Item Not Found.
- FSN is the product identifier.
- BIN is the warehouse shelf/location.
- Use StarRocks and NebulaGraph tools.
- Cite factual claims.
- End with a recommended action.

The prompt is like the assistant's job description.

Without this prompt, the LLM may behave like a generic chatbot.

With this prompt, it behaves more like a warehouse diagnosis assistant.

## Tool Calling

Tool calling means the LLM can ask the backend to run a function.

The LLM itself cannot directly access StarRocks or NebulaGraph.

So the backend gives it tools:

```text
query_starrocks
query_nebulagraph
```

If the assistant needs SQL data, it calls `query_starrocks`.

If it needs graph relationship data, it calls `query_nebulagraph`.

Simple flow:

```text
User question
-> LLM thinks
-> LLM calls tool
-> Backend runs query
-> Query result goes back to LLM
-> LLM writes answer with citations
```

## Citation

A citation is proof behind an answer.

Example:

```text
FSN-S2-001 failed across 3 distinct BINs [c1].
Recommended action: Replenish.
```

Here `[c1]` points to a real query result.

Citations are important because warehouse actions should not be based on random AI guesses.

## Guardrail

A guardrail is a safety check.

In this project, guardrails stop the LLM from running dangerous database queries.

For example, the assistant should be allowed to run:

```sql
SELECT ...
```

But it should not be allowed to run:

```sql
DELETE ...
DROP TABLE ...
UPDATE ...
```

Guardrails sit between the LLM and the database.

## Timeout

A timeout is a time budget.

The assistant cannot keep thinking forever.

The current settings are:

```text
FAST mode = 10 seconds
THOROUGH mode = 30 seconds
maximum tool loops = 12
```

If time runs out, the backend can return a partial answer or synthesize an answer from the citations already collected.

## OpenAI-Compatible API

The project uses Ollama locally, but the Python client is the OpenAI client.

This works because Ollama exposes an OpenAI-compatible API.

So the code can use:

```python
from openai import OpenAI
```

while still talking to:

```text
http://localhost:11434/v1
```

This makes the integration simpler and keeps the code close to common LLM client patterns.
