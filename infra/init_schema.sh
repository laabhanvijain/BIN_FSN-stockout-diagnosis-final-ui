#!/usr/bin/env bash
# infra/init_schema.sh
# =====================
# Applies StarRocks DDL and NebulaGraph schema by running commands
# INSIDE the containers — no mysql/curl/nebula-console needed on the host.
#
# Usage:
#   bash infra/init_schema.sh
#
# Safe to re-run — all statements use IF NOT EXISTS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[init]${NC} $*"; }
warn()  { echo -e "${YELLOW}[init]${NC} $*"; }
error() { echo -e "${RED}[init]${NC} $*"; exit 1; }

# ── wait for StarRocks (exec mysql inside the container) ──────────────────────

wait_starrocks() {
  info "Waiting for StarRocks (starrocks-fe container) …"
  local attempts=0
  until docker exec starrocks-fe \
        mysql -uroot -h127.0.0.1 -P9030 -e "SELECT 1" &>/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ $attempts -ge 36 ]; then
      error "StarRocks not reachable after 3 minutes. Is docker compose up?"
    fi
    warn "  not ready yet (attempt ${attempts}/36) …"
    sleep 5
  done
  info "StarRocks is ready."
}

# ── wait for NebulaGraph (exec nc inside storaged which has busybox) ──────────

wait_nebula() {
  # Test connectivity via the backend container (same Docker network as graphd).
  # This avoids curl/nc issues inside the stripped-down nebula image itself.
  info "Waiting for NebulaGraph graphd (port 9669) …"
  local attempts=0
  until docker exec backend python3 -c \
        "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(s.connect_ex(('nebula-graphd',9669)))" \
        &>/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ $attempts -ge 36 ]; then
      error "NebulaGraph not reachable after 3 minutes. Is docker compose up?"
    fi
    warn "  not ready yet (attempt ${attempts}/36) …"
    sleep 5
  done
  info "NebulaGraph is ready."
}

# ── apply StarRocks DDL (copy SQL into container then run it) ─────────────────

apply_starrocks() {
  info "Applying StarRocks schema …"
  docker cp "${REPO_ROOT}/data/schema/starrocks.sql" starrocks-fe:/tmp/starrocks.sql
  docker exec starrocks-fe \
    mysql -uroot -h127.0.0.1 -P9030 < /dev/null -e "$(docker exec starrocks-fe cat /tmp/starrocks.sql)" \
    || docker exec starrocks-fe \
       sh -c 'mysql -uroot -h127.0.0.1 -P9030 < /tmp/starrocks.sql'
  info "StarRocks schema applied."
}

# ── apply NebulaGraph schema via Python inside the backend container ──────────

apply_nebula() {
  info "Applying NebulaGraph schema via backend container …"
  docker cp "${REPO_ROOT}/data/schema/nebula.ngql" backend:/tmp/nebula.ngql
  docker exec backend python3 - <<'PYEOF'
import time, sys
from nebula3.Config import Config
from nebula3.gclient.net import ConnectionPool

cfg = Config()
cfg.max_connection_pool_size = 1
pool = ConnectionPool()

# Retry connection a few times (graphd may still be warming up)
for attempt in range(10):
    if pool.init([("nebula-graphd", 9669)], cfg):
        break
    print(f"  NebulaGraph not ready, retry {attempt+1}/10 …")
    time.sleep(3)
else:
    print("ERROR: Could not connect to NebulaGraph", file=sys.stderr)
    sys.exit(1)

session = pool.get_session("root", "nebula")

with open("/tmp/nebula.ngql") as f:
    raw = f.read()

for stmt in raw.split(";"):
    stmt = stmt.strip()
    if not stmt or stmt.startswith("--") or stmt.startswith("#"):
        continue
    result = session.execute(stmt + ";")
    short = stmt[:80].replace("\n", " ")
    if not result.is_succeeded():
        print(f"  WARN: {result.error_msg()[:80]}  (stmt: {short})")
    else:
        print(f"  OK: {short}")

session.release()
pool.close()
print("NebulaGraph schema applied.")
PYEOF
  info "NebulaGraph schema applied."
}

# ── main ──────────────────────────────────────────────────────────────────────

main() {
  info "=== BIN-FSN Stockout Diagnosis — Schema Init ==="
  wait_starrocks
  wait_nebula
  apply_starrocks
  apply_nebula
  info "=== Schema init complete. Run next: ==="
  info "    python data/generate_dummy_data.py --clear"
}

main "$@"
