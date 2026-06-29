# 06 · LLM Assistant

> Milestone: M7. Detail: [../deliverables/LLD/07-llm-agent.md](../deliverables/LLD/07-llm-agent.md).

_Status: M7 done 2026-06-26._

---

## 2026-06-26 — M7 complete: LLM assistant (POST /ask)

### What was done

**Two-stage pipeline (`backend/services/llm.py`)**

Stage 1 — Haiku 4.5 routing: classifies the question into `SQL_ONLY`, `GRAPH_ONLY`,
`SQL_GRAPH`, or `OUT_OF_SCOPE` using a single Anthropic call with `max_tokens=10`.
The tag restricts which tools Sonnet receives, avoiding wasted graph calls for
pure-SQL questions and skipping Sonnet entirely for out-of-scope ones.

Stage 2 — Sonnet 4.5 reasoning: agentic tool loop (max 8 rounds). Each round,
Sonnet decides which tool to call (`run_sql` or `run_ngql`), the backend executes
it (with a keyword deny-list security check), returns results as a `tool_result`
message, and Sonnet continues until it produces a final answer with a mandatory
`---CITATIONS---` block.

**Security layers**:
- SQL/nGQL keyword deny-list regex blocks all DML/DDL before execution.
- Error strings returned to the model (not the user) — Sonnet self-corrects.
- Row cap at 50 keeps context size bounded.
- Hard cap of 8 tool rounds prevents runaway loops.

**Citation enforcement**:
- System prompt mandates `---CITATIONS---` block format.
- Post-processing appends a ⚠️ warning if the block is missing.

**`backend/routers/ask.py`**
- `POST /api/ask` with Pydantic request/response models.
- 503 gate: returns `HTTPException(503)` if `ANTHROPIC_API_KEY` is empty.
- `question` validated: min 3, max 500 chars.

### Technical decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Two-stage (Haiku + Sonnet) | Separate models per task | Haiku routes cheaply; Sonnet reasons powerfully |
| `max_tokens=10` for Haiku | Hard limit | Prevents anything but a tag in the response |
| Max 8 tool rounds | Hard cap | Stays under 10s SLA; prevents runaway |
| Regex deny-list on SQL/nGQL | Keyword blocking | LLM generates free-text queries; must sanitise |
| Error to model, not user | Return in `tool_result` | Model self-corrects; user sees clean answer |
| Citation post-process warning | ⚠️ badge in answer | Defense-in-depth against model forgetfulness |

### Files changed

- Created: `backend/services/llm.py`, `backend/routers/ask.py`
- Updated: `backend/main.py`

### Status: committed 2026-06-26

<!-- ## YYYY-MM-DD — <what happened> -->
