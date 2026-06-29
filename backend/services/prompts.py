"""
backend/services/prompts.py
============================
System prompts and investigation playbooks for the LLM agent.
"""


def build_system_prompt(warehouse_id: str) -> str:
    """Build the main system prompt for the LLM agent."""
    return f"""You are an expert warehouse operations analyst for a dark-store fulfillment system.

Your role: diagnose pick failures (INF = Item Not Found) and recommend actions.

**Warehouse context:**
- Warehouse ID: {warehouse_id}
- Items (FSN) are stored in physical slots (BIN)
- When a picker can't find an FSN at its assigned BIN, they raise an INF
- This creates an IRT (Inventory Resolution Ticket)

**Available tools:**
1. `query_starrocks` — run SQL on StarRocks analytics database
2. `query_nebulagraph` — run nGQL graph traversal

**Diagnostic framework:**

**PHANTOM INVENTORY** (≥3 distinct FSNs failing in one BIN):
- Many different items missing from the same slot
- Action: Stocktake the BIN (physical audit)
- Possible causes: mislabeling, theft, putaway errors

**GENUINE STOCKOUT** (≥2 distinct BINs failing for one FSN):
- Same item missing across multiple locations
- Action: Replenish the FSN
- Possible causes: depleted inventory, demand spike

**DUAL** (both thresholds met):
- Action: Both stocktake AND replenish

**AMBIGUOUS** (neither threshold met):
- Requires upstream investigation (see below)

**AMBIGUOUS investigation checklist:**
When verdict is AMBIGUOUS, investigate in order:

Step A: Check inventory_items table
```sql
SELECT fsn, atp, quantity, storage_location_label, flow, grn_id 
FROM inventory_items WHERE warehouse_id = '{warehouse_id}' AND fsn = 'FSN-X'
```

Step B: If inventory exists but INF occurred:
- If flow='RESERVATION' or atp=0 but quantity>0: check reservations table
- If grn_id IS NULL: **positive variance** → Stocktake

Step C: If inventory is zero or missing:
- Check goods_receipt_notes for inbound
- Check consignment_receiving_instances for putaway status
- If GRN exists but CRI not shelved: **Complete put-away**
- If no GRN at all: **Replenish**

**Graph signals (use when relevant):**
- Picker concentration: `MATCH (p:Picker)-[:ASSIGNED_TO]->(b:BIN) WHERE id(b) == "WH:BIN-LABEL"`
- Shared inbound batch: `MATCH (f:FSN)-[:FAILED_AT]->(b:BIN), (f)-[:RECEIVED_IN]->(g:GRN) WHERE id(b) == "WH:BIN-LABEL"`
- Reservation trace: `GO FROM "FSN:FSN-X" OVER RESERVED_BY YIELD dst(edge)`

**Critical rules:**
1. ALWAYS cite every factual claim with [c1], [c2], etc. matching tool results
2. NEVER recommend Replenish for missing inventory until you've checked goods_receipt_notes and consignment_receiving_instances
3. NEVER answer from memory — only from tool results
4. End EVERY answer with "Recommended action: <action>"
5. If the question lacks a BIN or FSN, ask the user to specify

**Output format:**
<analysis>
<findings based on [c1], [c2], etc.>
</analysis>

Verdict: <PHANTOM/GENUINE/DUAL/AMBIGUOUS> (distinct FSNs=X, distinct bins=Y)
Recommended action: <Stocktake/Replenish/etc.>
"""


def build_ambiguous_nudge(citations: list[dict]) -> str:
    """
    Build a nudge message to continue AMBIGUOUS investigation.
    
    Checks which steps have been completed and prompts for missing ones.
    """
    steps = _investigation_steps(citations)
    
    if not steps["inventory"]:
        return ("Step A incomplete: query inventory_items for the FSN to see "
                "atp, quantity, flow, grn_id.")
    
    if steps["inventory_empty"]:
        missing = []
        if not steps["reservation"]:
            missing.append("reservations")
        if not steps["inbound"]:
            missing.append("goods_receipt_notes and consignment_receiving_instances")
        
        if missing:
            return f"Inventory is zero. Check upstream: {', '.join(missing)}."
    
    else:
        # Inventory exists but INF occurred
        if not steps["inbound"] and _inventory_grn_id_null(citations):
            return ("Inventory exists but grn_id IS NULL — possible positive variance. "
                    "Check goods_receipt_notes to confirm.")
    
    return "Investigation complete. Summarize findings and recommend action."


def _investigation_steps(citations: list[dict]) -> dict:
    """
    Analyze which investigation steps have been completed.
    
    Returns:
        {
            "inventory": bool,
            "inventory_empty": bool,
            "reservation": bool,
            "inbound": bool,
        }
    """
    inventory_checked = False
    inventory_empty = False
    reservation_checked = False
    inbound_checked = False
    
    for c in citations:
        query = (c.get("query") or "").lower()
        
        if "inventory_items" in query:
            inventory_checked = True
            rows = c.get("rows") or []
            if not rows or all(int(r.get("quantity", 0)) == 0 for r in rows):
                inventory_empty = True
        
        if "reservation" in query:
            reservation_checked = True
        
        if "goods_receipt_notes" in query or "consignment_receiving" in query:
            inbound_checked = True
    
    return {
        "inventory": inventory_checked,
        "inventory_empty": inventory_empty,
        "reservation": reservation_checked,
        "inbound": inbound_checked,
    }


def _inventory_grn_id_null(citations: list[dict]) -> bool:
    """Check if any inventory_items row has grn_id IS NULL."""
    for c in citations:
        if "inventory_items" not in (c.get("query") or "").lower():
            continue
        for row in c.get("rows") or []:
            if row.get("grn_id") is None:
                return True
    return False
