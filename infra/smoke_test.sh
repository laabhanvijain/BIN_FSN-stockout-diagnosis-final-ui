#!/usr/bin/env bash
# infra/smoke_test.sh
# ====================
# Quick end-to-end smoke test against the running demo stack.
# Verifies: health, diagnoses verdicts, ask endpoint, feedback CRUD.
#
# Usage:
#   bash infra/smoke_test.sh
#   BACKEND_URL=http://localhost:8000 bash infra/smoke_test.sh

set -euo pipefail

BACKEND="${BACKEND_URL:-http://localhost:8000}"
WH="WH-BLR-001"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}  ✓${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; FAILURES=$((FAILURES+1)); }
section() { echo -e "\n${YELLOW}── $* ──${NC}"; }

FAILURES=0

# ── 1. Health ─────────────────────────────────────────────────────────────────
section "Health check"

STATUS=$(curl -sf "${BACKEND}/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "FAIL")
if [ "$STATUS" = "ok" ]; then
  pass "GET /health → ok"
else
  fail "GET /health returned: $STATUS"
fi

# ── 2. Diagnoses ──────────────────────────────────────────────────────────────
section "Diagnoses endpoint"

DIAG=$(curl -sf "${BACKEND}/api/diagnoses?warehouse_id=${WH}&window_days=1" 2>/dev/null || echo "[]")
COUNT=$(echo "$DIAG" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

if [ "$COUNT" -gt 0 ]; then
  pass "GET /api/diagnoses → ${COUNT} rows"
else
  fail "GET /api/diagnoses returned 0 rows (seed data missing?)"
fi

# Check expected verdicts are present
for VERDICT in PHANTOM_INVENTORY GENUINE_STOCKOUT DUAL AMBIGUOUS; do
  HIT=$(echo "$DIAG" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print(any(r['verdict'] == '$VERDICT' for r in rows))
" 2>/dev/null || echo "False")
  if [ "$HIT" = "True" ]; then
    pass "Verdict $VERDICT present"
  else
    fail "Verdict $VERDICT not found (check seed data)"
  fi
done

# ── 3. Feedback list ──────────────────────────────────────────────────────────
section "Feedback endpoint"

FB=$(curl -sf "${BACKEND}/api/feedback?warehouse_id=${WH}" 2>/dev/null || echo "[]")
FB_COUNT=$(echo "$FB" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
if [ "$FB_COUNT" -gt 0 ]; then
  pass "GET /api/feedback → ${FB_COUNT} rows"
else
  fail "GET /api/feedback returned 0 rows (seed recommendation_log missing?)"
fi

# Check failures_ceased is computed for verified rows
CEASED=$(echo "$FB" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
verified = [r for r in rows if r['status'] == 'verified' and r.get('failures_ceased') is not None]
print(len(verified))
" 2>/dev/null || echo 0)
if [ "$CEASED" -gt 0 ]; then
  pass "failures_ceased computed for ${CEASED} verified row(s)"
else
  fail "No verified rows with failures_ceased (check seeded recommendation_log)"
fi

# ── 4. Ask endpoint (no LLM key needed — just check it doesn't 500) ────────────
section "Ask endpoint (503 expected without API key, 200 with key)"

ASK_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${BACKEND}/api/ask" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"How many INF events does BIN-PHANTOM-A have?\", \"warehouse_id\": \"${WH}\"}" \
  2>/dev/null || echo "000")

if [ "$ASK_STATUS" = "200" ]; then
  pass "POST /api/ask → 200 (LLM key configured)"
elif [ "$ASK_STATUS" = "503" ]; then
  pass "POST /api/ask → 503 (no ANTHROPIC_API_KEY — expected in CI)"
else
  fail "POST /api/ask → ${ASK_STATUS} (unexpected)"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
if [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}All smoke tests passed.${NC}"
  exit 0
else
  echo -e "${RED}${FAILURES} smoke test(s) failed.${NC}"
  exit 1
fi
