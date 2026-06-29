"""
generate_dummy_data.py
======================
Seeds StarRocks with ground-truth test data for the BIN-FSN Stockout Diagnosis demo.

Run:
    python data/generate_dummy_data.py [--host localhost] [--port 9030]

Ground-truth scenarios
----------------------
S1  PHANTOM_INVENTORY   BIN-A   — 5 distinct FSNs fail in the same BIN
S2  GENUINE_STOCKOUT    FSN-X   — 1 FSN fails across 3 distinct BINs
S3  DUAL                BIN-B   — many FSNs fail AND one of them fails across many BINs
S4  PICKER_DRIVEN       BIN-C   — all picks assigned to the same picker (root cause: picker)
S5  SHARED_GRN          BIN-D   — all FSNs share the same inbound GRN batch
S6  NOISE / AMBIGUOUS   various — isolated single failures, no threshold met

The expected_verdicts dict at the bottom maps each (bin, fsn) cluster to its
intended verdict — use it to measure accuracy after seeding.
"""

import argparse
import datetime
import random
import sys
import uuid

import pymysql

# ── reproducibility ───────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)

WH = "WH-BLR-001"
BASE_DT = datetime.datetime.now() - datetime.timedelta(hours=6)  # within today's window


def _dt(offset_minutes: int) -> str:
    return (BASE_DT + datetime.timedelta(minutes=offset_minutes)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _irt() -> str:
    return str(uuid.uuid4())[:8].upper()


def _order() -> str:
    return "ORD-" + str(random.randint(100000, 999999))


# ── row builder ───────────────────────────────────────────────────────────────

def make_row(bin_label, fsn, picker, grn, offset_min):
    """Return a single pendency_mv row as a dict."""
    return {
        "reservation_warehouse_id": WH,
        "picklist_source_location_label": bin_label,
        "picklist_item_fsn": fsn,
        "irt_ticket_id": _irt(),
        "irt_ticket_type": "INF",
        "picklist_assigned_to": picker,
        "order_id": _order(),
        "grn_id": grn,
        "updated_at": _dt(offset_min),
    }


# ── scenario builders ─────────────────────────────────────────────────────────

def scenario_s1_phantom():
    """S1 — PHANTOM: 5 distinct FSNs failing in BIN-PHANTOM-A.
    Expected verdict: PHANTOM_INVENTORY (distinct_fsn_count >= threshold=3).
    """
    rows = []
    for i in range(1, 6):          # 5 distinct FSNs
        for j in range(2):         # 2 failures each for weight
            rows.append(make_row(
                bin_label="BIN-PHANTOM-A",
                fsn=f"FSN-S1-{i:03d}",
                picker="PKR-001",
                grn="GRN-BATCH-001",
                offset_min=i * 10 + j,
            ))
    return rows


def scenario_s2_genuine():
    """S2 — GENUINE_STOCKOUT: FSN-S2-001 fails in 3 distinct BINs.
    Expected verdict: GENUINE_STOCKOUT (distinct_bin_count >= threshold=2).
    """
    rows = []
    bins = ["BIN-GENUINE-A", "BIN-GENUINE-B", "BIN-GENUINE-C"]
    for idx, b in enumerate(bins):
        for j in range(3):         # 3 failures per BIN
            rows.append(make_row(
                bin_label=b,
                fsn="FSN-S2-001",
                picker=f"PKR-{idx + 10:03d}",
                grn="GRN-BATCH-002",
                offset_min=60 + idx * 5 + j,
            ))
    return rows


def scenario_s3_dual():
    """S3 — DUAL: BIN-DUAL-A has 4 distinct FSNs (PHANTOM signal) AND
    one of them (FSN-S3-CROSS) also fails in 2 other BINs (GENUINE signal).
    Expected verdict: DUAL.
    """
    rows = []
    # PHANTOM side: 4 FSNs in BIN-DUAL-A
    for i in range(1, 5):
        rows.append(make_row(
            bin_label="BIN-DUAL-A",
            fsn=f"FSN-S3-{i:03d}",
            picker="PKR-005",
            grn="GRN-BATCH-003",
            offset_min=120 + i,
        ))
    # GENUINE side: FSN-S3-001 also fails in two more BINs
    for b in ["BIN-DUAL-B", "BIN-DUAL-C"]:
        rows.append(make_row(
            bin_label=b,
            fsn="FSN-S3-001",
            picker="PKR-006",
            grn="GRN-BATCH-003",
            offset_min=130,
        ))
    return rows


def scenario_s4_picker():
    """S4 — PICKER_DRIVEN: 4 distinct FSNs in BIN-PICKER-A, all assigned to PKR-BAD.
    SQL verdict: PHANTOM (many FSNs, one BIN).
    Graph enrichment: picker_concentration=1.0 -> root cause = picker error.
    """
    rows = []
    for i in range(1, 5):
        for j in range(2):
            rows.append(make_row(
                bin_label="BIN-PICKER-A",
                fsn=f"FSN-S4-{i:03d}",
                picker="PKR-BAD",     # same picker for all
                grn="GRN-BATCH-004",
                offset_min=180 + i * 3 + j,
            ))
    return rows


def scenario_s5_shared_grn():
    """S5 — SHARED_GRN: 4 distinct FSNs in BIN-GRN-A, all from GRN-SHARED-999.
    SQL verdict: PHANTOM.
    Graph enrichment: all FSNs share one GRN -> root cause = bad inbound batch.
    """
    rows = []
    for i in range(1, 5):
        rows.append(make_row(
            bin_label="BIN-GRN-A",
            fsn=f"FSN-S5-{i:03d}",
            picker=f"PKR-{20 + i:03d}",
            grn="GRN-SHARED-999",    # same GRN for all
            offset_min=240 + i * 4,
        ))
    return rows


def scenario_s6_noise():
    """S6 — NOISE / AMBIGUOUS: isolated single failures, no thresholds met.
    Expected verdict: AMBIGUOUS.
    """
    rows = []
    # 2 random (bin, fsn) combos, 1 failure each
    rows.append(make_row("BIN-NOISE-1", "FSN-S6-001", "PKR-030", "GRN-BATCH-005", 300))
    rows.append(make_row("BIN-NOISE-2", "FSN-S6-002", "PKR-031", "GRN-BATCH-006", 305))
    return rows


def recommendation_log_rows():
    """Two already-resolved recommendation_log rows to demo the closed-loop view."""
    now = datetime.datetime(2026, 6, 25, 18, 0, 0)
    return [
        {
            "warehouse_id": WH,
            "bin": "BIN-PHANTOM-A",
            "fsn": "FSN-S1-001",
            "verdict": "PHANTOM_INVENTORY",
            "action": "stocktake",
            "status": "verified",
            "suggested_at": "2026-06-25 12:00:00",
            "resolved_at": "2026-06-25 15:00:00",
            "evidence_ref": "SELECT distinct_fsn_count=5 FROM pendency_mv WHERE bin=BIN-PHANTOM-A",
            "failures_before": 10,
            "failures_after": 0,
        },
        {
            "warehouse_id": WH,
            "bin": "BIN-GENUINE-A",
            "fsn": "FSN-S2-001",
            "verdict": "GENUINE_STOCKOUT",
            "action": "replenish",
            "status": "verified",
            "suggested_at": "2026-06-25 12:30:00",
            "resolved_at": "2026-06-25 16:00:00",
            "evidence_ref": "SELECT distinct_bin_count=3 FROM pendency_mv WHERE fsn=FSN-S2-001",
            "failures_before": 9,
            "failures_after": 1,
        },
    ]


# ── expected verdicts (ground-truth map for accuracy measurement) ─────────────

EXPECTED_VERDICTS = {
    ("BIN-PHANTOM-A", "*"):    "PHANTOM_INVENTORY",
    ("*", "FSN-S2-001"):       "GENUINE_STOCKOUT",
    ("BIN-DUAL-A", "*"):       "DUAL",
    ("BIN-PICKER-A", "*"):     "PHANTOM_INVENTORY",  # SQL; graph adds PICKER_DRIVEN root cause
    ("BIN-GRN-A", "*"):        "PHANTOM_INVENTORY",  # SQL; graph adds SHARED_GRN root cause
    ("BIN-NOISE-1", "*"):      "AMBIGUOUS",
    ("BIN-NOISE-2", "*"):      "AMBIGUOUS",
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def connect(host: str, port: int) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=host,
        port=port,
        user="root",
        password="",
        database="hl_customer_outbound",
        connect_timeout=10,
    )


def insert_pendency_rows(conn, rows: list[dict]) -> None:
    sql = """
        INSERT INTO pendency_mv (
            reservation_warehouse_id, picklist_source_location_label,
            picklist_item_fsn, irt_ticket_id, irt_ticket_type,
            picklist_assigned_to, order_id, grn_id, updated_at
        ) VALUES (
            %(reservation_warehouse_id)s, %(picklist_source_location_label)s,
            %(picklist_item_fsn)s, %(irt_ticket_id)s, %(irt_ticket_type)s,
            %(picklist_assigned_to)s, %(order_id)s, %(grn_id)s, %(updated_at)s
        )
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def insert_rec_log_rows(conn, rows: list[dict]) -> None:
    # Assign an id to each row (StarRocks DUPLICATE KEY requires all key cols)
    import time as _time
    for i, row in enumerate(rows):
        if "id" not in row:
            row["id"] = int(_time.time() * 1000) + i
    sql = """
        INSERT INTO recommendation_log (
            id, warehouse_id, bin, fsn, verdict, action, status,
            suggested_at, resolved_at, evidence_ref,
            failures_before, failures_after
        ) VALUES (
            %(id)s, %(warehouse_id)s, %(bin)s, %(fsn)s, %(verdict)s, %(action)s, %(status)s,
            %(suggested_at)s, %(resolved_at)s, %(evidence_ref)s,
            %(failures_before)s, %(failures_after)s
        )
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def clear_tables(conn) -> None:
    # StarRocks requires a WHERE clause for DELETE; TRUNCATE is the correct way
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE pendency_mv")
        cur.execute("TRUNCATE TABLE recommendation_log")
    conn.commit()


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed StarRocks with BIN-FSN demo data")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--clear", action="store_true", help="DELETE existing rows before seeding")
    args = parser.parse_args()

    print(f"Connecting to StarRocks at {args.host}:{args.port} ...")
    conn = connect(args.host, args.port)
    print("Connected.")

    if args.clear:
        print("Clearing existing data ...")
        clear_tables(conn)

    all_rows = (
        scenario_s1_phantom()
        + scenario_s2_genuine()
        + scenario_s3_dual()
        + scenario_s4_picker()
        + scenario_s5_shared_grn()
        + scenario_s6_noise()
    )

    print(f"Inserting {len(all_rows)} pendency_mv rows across 6 scenarios ...")
    insert_pendency_rows(conn, all_rows)

    rec_rows = recommendation_log_rows()
    print(f"Inserting {len(rec_rows)} recommendation_log rows ...")
    insert_rec_log_rows(conn, rec_rows)

    conn.close()

    print("\nDone. Ground-truth verdict map:")
    for k, v in EXPECTED_VERDICTS.items():
        print(f"  {k[0]:20s}  {k[1]:15s}  →  {v}")

    print(
        "\nVerify with PS validation SQL:\n"
        "  SELECT picklist_source_location_label AS bin,\n"
        "         COUNT(DISTINCT picklist_item_fsn) AS distinct_fsn,\n"
        "         COUNT(DISTINCT picklist_source_location_label) AS distinct_bin\n"
        "  FROM   hl_customer_outbound.pendency_mv\n"
        "  WHERE  irt_ticket_id IS NOT NULL\n"
        "  GROUP BY bin;"
    )


if __name__ == "__main__":
    main()
