"""
backend/services/agent.py
==========================
LLM agent with tool-calling loop for stockout diagnosis.

Architecture:
- Single-model (Ollama) tool loop with query_starrocks and query_nebulagraph tools
- Deterministic fallbacks for weaker models (auto-bootstrap, SQL extraction, graph auto-trace)
- Citation enforcement and answer synthesis
- Timeout and iteration limits

Key differences from Anthropic version:
- No two-stage routing (Haiku/Sonnet)
- More defensive: handles SQL-in-prose, hallucinations, incomplete answers
- Graph signals queried dynamically by LLM, not pre-computed
"""

import json
import re
import time
import uuid
import logging
from backend.config import settings
from backend.services import llm, prompts, guards
from backend.db.starrocks import get_connection
from backend.db.nebula import get_session

logger = logging.getLogger(__name__)

# Tool definitions in OpenAI format
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "query_starrocks",
            "description": "Execute a SELECT query on StarRocks analytics database",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL SELECT query to execute"
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_nebulagraph",
            "description": "Execute a read-only nGQL query on NebulaGraph",
            "parameters": {
                "type": "object",
                "properties": {
                    "ngql": {
                        "type": "string",
                        "description": "nGQL query (MATCH, GO, FETCH, LOOKUP, etc.)"
                    }
                },
                "required": ["ngql"]
            }
        }
    }
]

_KNOWN_TOOLS = {"query_starrocks", "query_nebulagraph"}


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_starrocks(sql: str, warehouse_id: str) -> dict:
    """Execute SQL on StarRocks with guardrails."""
    # Validate query
    is_valid, error = guards.validate_sql(sql, warehouse_id)
    if not is_valid:
        return {"ok": False, "error": error, "query": sql}
    
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                # Cap at 50 rows
                rows = rows[:50] if rows else []
                return {
                    "ok": True,
                    "engine": "starrocks",
                    "query": sql,
                    "row_count": len(rows),
                    "rows": rows,
                }
        finally:
            conn.close()
    except Exception as e:
        logger.exception("StarRocks query failed: %s", sql[:200])
        return {"ok": False, "error": str(e), "query": sql}


def _execute_nebulagraph(ngql: str, warehouse_id: str) -> dict:
    """Execute nGQL on NebulaGraph with guardrails."""
    # Validate query
    is_valid, error = guards.validate_ngql(ngql)
    if not is_valid:
        return {"ok": False, "error": error, "query": ngql}
    
    try:
        with get_session() as session:
            if session is None:
                return {"ok": False, "error": "NebulaGraph session unavailable", "query": ngql}
            
            full_query = f"USE {settings.nebula_space};\n{ngql}"
            result = session.execute(full_query)
            
            if not result.is_succeeded():
                return {"ok": False, "error": result.error_msg(), "query": ngql}
            
            # Convert result to list of dicts
            rows = []
            for i in range(min(result.row_size(), 50)):  # Cap at 50
                row_vals = result.row_values(i)
                row = {}
                for j, col_name in enumerate(result.keys()):
                    val = row_vals[j]
                    # Convert nebula types to Python types
                    row[col_name] = str(val) if val is not None else None
                rows.append(row)
            
            return {
                "ok": True,
                "engine": "nebulagraph",
                "query": ngql,
                "row_count": len(rows),
                "rows": rows,
            }
    except Exception as e:
        logger.exception("NebulaGraph query failed: %s", ngql[:200])
        return {"ok": False, "error": str(e), "query": ngql}


def execute_tool(tool_name: str, arguments: dict, warehouse_id: str) -> dict:
    """Execute a tool call and return the result."""
    if tool_name == "query_starrocks":
        sql = arguments.get("sql", "")
        return _execute_starrocks(sql, warehouse_id)
    elif tool_name == "query_nebulagraph":
        ngql = arguments.get("ngql", "")
        return _execute_nebulagraph(ngql, warehouse_id)
    else:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}


# ── Text parsing helpers (for weaker models) ──────────────────────────────────

def _sanitize_llm_text(text: str) -> str:
    """Strip role prefix lines like 'assistant' from model output."""
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").split("\n")
    while lines:
        head = lines[0].strip().lower().rstrip(":")
        if head in ("assistant", "user", "system"):
            lines.pop(0)
            while lines and not lines[0].strip():
                lines.pop(0)
            continue
        break
    return "\n".join(lines).strip()


def _extract_json_objects(text: str) -> list[dict]:
    """Extract JSON objects from text (for tool calls in prose)."""
    objs, i = [], 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth, start, in_str, escape = 0, i, False, False
        for j in range(i, len(text)):
            c = text[j]
            if escape:
                escape = False
                continue
            if c == "\\" and in_str:
                escape = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        objs.append(json.loads(text[start:j + 1]))
                    except json.JSONDecodeError:
                        pass
                    i = j + 1
                    break
        else:
            i += 1
    return objs


def _parse_text_tool_calls(content: str) -> list[dict]:
    """Recover tool calls when model writes JSON in content instead of tool_calls."""
    if not content:
        return []
    calls, seen = [], set()
    for obj in _extract_json_objects(content):
        name = obj.get("name", "")
        if name not in _KNOWN_TOOLS:
            continue
        args = obj.get("parameters") or obj.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        
        # Validate required args
        if name == "query_starrocks" and not args.get("sql"):
            continue
        if name == "query_nebulagraph" and not args.get("ngql"):
            continue
        
        key = (name, json.dumps(args, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        calls.append({"id": f"text-{uuid.uuid4().hex[:8]}", "name": name, "arguments": args})
    return calls


def _normalize_tool_calls(msg) -> list[dict]:
    """Extract tool calls from OpenAI message (native or text-embedded)."""
    if msg.tool_calls:
        out = []
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            out.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return out
    return _parse_text_tool_calls(msg.content)


# ── Pattern detection helpers ─────────────────────────────────────────────────

_FSN_RE = re.compile(r"FSN-[A-Z0-9]+", re.I)
_BIN_RE = re.compile(r"\bbin\s+([A-Z][\w-]+)", re.I)


def _extract_fsn(text: str) -> str | None:
    """Extract FSN from text."""
    m = _FSN_RE.search(text or "")
    return guards.normalize_fsn(m.group(0)) if m else None


def _extract_bin(text: str) -> str | None:
    """Extract BIN label from text."""
    m = _BIN_RE.search(text or "")
    return m.group(1) if m else None


def _looks_like_unparsed_tool(content: str) -> bool:
    """Check if content contains JSON tool call that wasn't parsed."""
    return bool(content and re.search(r'"name"\s*:\s*"query_\w+"', content))


def _looks_like_sql_in_content(content: str) -> bool:
    """Check if model pasted SQL in prose instead of calling tool."""
    if not content:
        return False
    low = content.lower()
    return "select " in low and " from " in low


def _extract_sql_from_content(content: str) -> list[str]:
    """Extract SELECT statements from prose."""
    if not content:
        return []
    seen, out = set(), []
    for m in re.finditer(r"\bSELECT\b.+?;", content, re.I | re.S):
        sql = m.group(0).strip().rstrip(";").strip()
        key = sql.lower()
        if key not in seen:
            seen.add(key)
            out.append(sql)
    return out


def _asks_for_clarification(content: str) -> bool:
    """Check if model is asking for more info."""
    if not content:
        return False
    low = content.lower()
    return bool(re.search(r"\b(which|what) (bin|fsn|item)\b|please (specify|provide)|need (a|the) (bin|fsn)\b", low))


def _hallucinated_answer(content: str, citations: list) -> bool:
    """Detect when model claims findings without any tool results."""
    if citations or not content or _asks_for_clarification(content):
        return False
    low = content.lower()
    if any(m in low for m in ("nebulagraph", "starrocks", "graph", "based on [c")):
        return True
    return bool(re.search(r"\b(infer|found|shows|indicates|suggests)\b", low) and len(content) > 80)


def _looks_like_incomplete_answer(content: str) -> bool:
    """Check if answer is incomplete or placeholder."""
    if not content or not content.strip():
        return True
    low = content.strip().lower()
    if any(phrase in low for phrase in ["please wait", "please let me know", "will now perform", "when you are ready"]):
        return True
    if "recommended action:" not in low and ("go from \"" in low or "go from '" in low):
        return True
    if _looks_like_sql_in_content(content) and "recommended action:" not in low:
        return True
    return False


# ── Verdict extraction ────────────────────────────────────────────────────────

def _extract_verdict_counts(citations: list[dict]) -> tuple[int | None, int | None]:
    """Extract distinct_fsns and distinct_bins from SQL results."""
    bin_fsns = fsn_bins = None
    for c in citations:
        if c.get("engine") != "starrocks":
            continue
        q = (c.get("query") or "").lower()
        rows = c.get("rows") or []
        if not rows or len(rows[0]) != 1:
            continue
        try:
            n = int(next(iter(rows[0].values())))
        except (TypeError, ValueError):
            continue
        key = next(iter(rows[0].keys())).lower()
        if "distinct_fsns" in key or (
            "distinct picklist_item_fsn" in q and not re.search(r"picklist_item_fsn\s*=", q)
        ):
            bin_fsns = n
        elif "distinct_bins" in key or (
            "distinct picklist_source_location_label" in q and re.search(r"picklist_item_fsn\s*=", q)
        ):
            fsn_bins = n
    return bin_fsns, fsn_bins


def _verdict_summary(bin_fsns: int | None, fsn_bins: int | None) -> tuple[str, str] | None:
    """Compute verdict from counts."""
    if bin_fsns is None and fsn_bins is None:
        return None
    phantom = (bin_fsns or 0) >= settings.phantom_fsn_threshold
    genuine = (fsn_bins or 0) >= settings.stockout_bin_threshold
    if phantom and genuine:
        return "DUAL", "Stocktake and Replenish"
    if phantom:
        return "PHANTOM", "Stocktake"
    if genuine:
        return "GENUINE_STOCKOUT", "Replenish"
    return "AMBIGUOUS", None


def _is_ambiguous_verdict(citations: list[dict]) -> bool:
    """Check if verdict is AMBIGUOUS."""
    bin_fsns, fsn_bins = _extract_verdict_counts(citations)
    if bin_fsns is None and fsn_bins is None:
        return False
    summary = _verdict_summary(bin_fsns, fsn_bins)
    return bool(summary and summary[0] == "AMBIGUOUS")


# ── Auto-bootstrap (deterministic helper) ─────────────────────────────────────

def _auto_bootstrap_verdict(question: str, warehouse_id: str, citations: list, messages: list) -> bool:
    """
    Auto-run verdict SQL when user mentions both FSN and BIN.
    
    This is a deterministic fallback for when the model doesn't immediately start querying.
    """
    if citations:
        return False
    
    fsn = _extract_fsn(question)
    bin_label = _extract_bin(question)
    if not fsn or not bin_label:
        return False
    
    wh = warehouse_id
    pending = [
        (
            f"SELECT COUNT(DISTINCT picklist_item_fsn) AS distinct_fsns FROM pendency_mv "
            f"WHERE reservation_warehouse_id = '{wh}' AND picklist_source_location_label = '{bin_label}' "
            f"AND irt_ticket_id IS NOT NULL"
        ),
        (
            f"SELECT COUNT(DISTINCT picklist_source_location_label) AS distinct_bins FROM pendency_mv "
            f"WHERE reservation_warehouse_id = '{wh}' AND picklist_item_fsn = '{fsn}' "
            f"AND irt_ticket_id IS NOT NULL"
        ),
        (
            f"SELECT fsn, atp, quantity, storage_location_label, flow, grn_id FROM inventory_items "
            f"WHERE warehouse_id = '{wh}' AND fsn = '{fsn}' LIMIT 10"
        ),
    ]
    
    for sql in pending:
        tc = {"id": f"auto-{uuid.uuid4().hex[:8]}", "name": "query_starrocks", "arguments": {"sql": sql}}
        _run_tool(tc, warehouse_id, citations, messages)
    
    messages.append({
        "role": "system",
        "content": (
            "Bootstrap queries loaded [c1, c2, c3]. "
            "Summarize verdict (distinct_fsns, distinct_bins) and inventory state. "
            "End with: Recommended action: <action>"
        ),
    })
    return True


# ── Tool execution wrapper ────────────────────────────────────────────────────

def _run_tool(tc: dict, warehouse_id: str, citations: list, messages: list):
    """Execute a tool call and append result to messages and citations."""
    args = tc["arguments"] if isinstance(tc.get("arguments"), dict) else {}
    result = execute_tool(tc["name"], args, warehouse_id)
    
    cid = f"c{len(citations) + 1}"
    if result.get("ok"):
        citations.append({
            "id": cid,
            "engine": result["engine"],
            "query": result["query"],
            "row_count": result["row_count"],
            "rows": result["rows"],
        })
        tool_payload = {
            "citation_id": cid,
            "row_count": result["row_count"],
            "rows": result["rows"],
        }
    else:
        tool_payload = {"error": result.get("error"), "query": result.get("query")}
    
    messages.append({
        "role": "tool",
        "tool_call_id": tc["id"],
        "content": json.dumps(tool_payload, default=str),
    })


# ── Answer synthesis ──────────────────────────────────────────────────────────

def _synthesize_answer(citations: list, question: str) -> str:
    """Build answer from citation rows when model output is incomplete."""
    lines = []
    bin_fsns, fsn_bins = _extract_verdict_counts(citations)
    summary = _verdict_summary(bin_fsns, fsn_bins)
    
    if bin_fsns is not None or fsn_bins is not None:
        verdict = summary[0] if summary else "AMBIGUOUS"
        lines.append(
            f"Verdict: {verdict} (distinct FSNs={bin_fsns}, distinct bins={fsn_bins})."
        )
    
    # Summarize key findings
    seen = set()
    for c in citations:
        cid = c.get("id", "")
        q = (c.get("query") or "").lower()
        rows = c.get("rows") or []
        
        if "inventory_items" in q and rows and "inventory" not in seen:
            seen.add("inventory")
            row = rows[0]
            lines.append(
                f"[{cid}] inventory: atp={row.get('atp')}, qty={row.get('quantity')}, "
                f"flow={row.get('flow')}, grn_id={row.get('grn_id')}"
            )
        elif "picker" in q and "picker" not in seen:
            seen.add("picker")
            lines.append(f"[{cid}] picker concentration detected")
        elif "grn" in q and "grn" not in seen:
            seen.add("grn")
            lines.append(f"[{cid}] inbound: {c.get('row_count', 0)} row(s)")
    
    if summary and summary[1]:
        lines.append(f"Recommended action: {summary[1]}")
    elif lines:
        lines.append("Recommended action: Investigate upstream")
    
    return "\n".join(lines) if lines else "No findings from citations."


# ── Main agent loop ───────────────────────────────────────────────────────────

def ask(question: str, warehouse_id: str, depth_mode: str = "FAST") -> dict:
    """
    Main entry point for LLM agent.
    
    Args:
        question: User question
        warehouse_id: Warehouse scope
        depth_mode: FAST (10s) or THOROUGH (30s)
    
    Returns:
        {
            "answer": str,
            "citations": list[dict],
            "partial": bool,
            "iterations": int,
            "elapsed_ms": int,
        }
    """
    budget = (
        settings.ask_thorough_timeout_ms
        if depth_mode == "THOROUGH"
        else settings.ask_total_timeout_ms
    )
    start = time.time()
    
    def elapsed_ms():
        return int((time.time() - start) * 1000)
    
    system = prompts.build_system_prompt(warehouse_id)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    citations = []
    iterations = 0
    
    # Try auto-bootstrap for common question patterns
    if _auto_bootstrap_verdict(question, warehouse_id, citations, messages):
        iterations = 1
    
    # Main tool loop
    for i in range(settings.ask_max_iterations):
        iterations = max(iterations, i + 1)
        if elapsed_ms() > budget:
            break
        
        try:
            resp = llm.chat(messages, tools=TOOL_SPECS)
        except Exception as e:
            logger.exception("LLM call failed")
            return {
                "answer": f"Error calling LLM: {e}",
                "citations": citations,
                "partial": True,
                "iterations": iterations,
                "elapsed_ms": elapsed_ms(),
            }
        
        msg = resp.choices[0].message
        tool_calls = _normalize_tool_calls(msg)
        
        if not tool_calls:
            # Model returned text without tools
            if _looks_like_unparsed_tool(msg.content):
                # Model wrote JSON but didn't use tool API
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({
                    "role": "system",
                    "content": "Use the tool API — call query_starrocks or query_nebulagraph. Don't echo JSON."
                })
                continue
            
            if _looks_like_sql_in_content(msg.content):
                # Model pasted SQL in prose
                ran = False
                for sql in _extract_sql_from_content(msg.content):
                    tc = {"id": f"auto-{uuid.uuid4().hex[:8]}", "name": "query_starrocks", "arguments": {"sql": sql}}
                    _run_tool(tc, warehouse_id, citations, messages)
                    ran = True
                if ran:
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    messages.append({"role": "system", "content": "SQL auto-executed. Summarize results and end with Recommended action:"})
                    continue
            
            if _hallucinated_answer(msg.content, citations):
                # Model claimed findings without querying
                messages.append({"role": "assistant", "content": msg.content or ""})
                messages.append({
                    "role": "system",
                    "content": "You have no tool results yet. Call query_starrocks or query_nebulagraph before making claims."
                })
                continue
            
            # Model is done
            answer = _sanitize_llm_text(msg.content or "")
            if _looks_like_incomplete_answer(answer) and citations:
                answer = _synthesize_answer(citations, question)
            
            return {
                "answer": answer,
                "citations": citations,
                "partial": False,
                "iterations": iterations,
                "elapsed_ms": elapsed_ms(),
            }
        
        # Model called tools
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                }
                for tc in tool_calls
            ],
        })
        
        for tc in tool_calls:
            _run_tool(tc, warehouse_id, citations, messages)
    
    # Loop exhausted or timeout
    if citations:
        final = _synthesize_answer(citations, question)
    else:
        final = "No data retrieved. Try including an FSN or BIN in your question."
    
    return {
        "answer": final,
        "citations": citations,
        "partial": elapsed_ms() > budget,
        "iterations": iterations,
        "elapsed_ms": elapsed_ms(),
    }
