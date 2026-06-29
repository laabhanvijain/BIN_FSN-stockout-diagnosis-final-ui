"""
data/data_generator.py
=======================
Continuous data generator for simulating live warehouse events.

Event rotation:
    repeat → repeat → inventory_adjust → new_bin → new_fsn

Usage:
    python data/data_generator.py              # Run continuously
    python data/data_generator.py --once       # Single batch
    python data/data_generator.py --interval 5 # Custom interval (seconds)
"""

import sys
import time
import json
import argparse
import random
from pathlib import Path
from datetime import datetime
import pymysql

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings

# State file
STATE_FILE = Path(__file__).parent / ".data_generator_state.json"

# Event types
EVENTS = ["repeat", "repeat", "inventory_adjust", "new_bin", "new_fsn"]

# Seeded FSNs (from generate_dummy_data.py)
SEEDED_FSNS = [
    "FSN-P1-001", "FSN-P1-002", "FSN-P1-003", "FSN-P1-004", "FSN-P1-005",
    "FSN-G1-001",
    "FSN-DUAL-001",
    "FSN-PICKER-001",
    "FSN-GRN-001", "FSN-GRN-002",
    "FSN-S1-001",
]

SEEDED_BINS = [
    "BIN-PHANTOM-A",
    "BIN-GENUINE-A", "BIN-GENUINE-B", "BIN-GENUINE-C",
    "BIN-DUAL-A",
    "BIN-PICKER-A",
    "BIN-GRN-A",
    "BIN-NOISE-A",
]


def load_state() -> dict:
    """Load generator state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "tick": 0,
        "fsn_seq": 1,
        "bin_seq": 1,
        "order_seq": 1000,
        "last_event": None,
    }


def save_state(state: dict):
    """Save generator state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_connection():
    """Get database connection."""
    return pymysql.connect(
        host=settings.starrocks_host,
        port=settings.starrocks_port,
        user=settings.starrocks_user,
        password=settings.starrocks_password or "",
        database=settings.starrocks_database,
        cursorclass=pymysql.cursors.DictCursor,
    )


def generate_repeat_event(conn, state: dict):
    """
    Repeat event: Create new INF for existing seeded FSN/BIN.
    
    This reinforces existing patterns (PHANTOM bins get more failures).
    """
    fsn = random.choice(SEEDED_FSNS)
    bin_label = random.choice(SEEDED_BINS)
    
    order_id = f"ORD-GEN-{state['order_seq']}"
    state['order_seq'] += 1
    
    irt_id = f"IRT-GEN-{state['tick']}-{random.randint(1000, 9999)}"
    picker = random.choice(["PKR-001", "PKR-002", "PKR-003"])
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert INF row
    with conn.cursor() as cur:
        sql = """
        INSERT INTO pendency_mv (
            reservation_warehouse_id, picklist_source_location_label,
            picklist_item_fsn, irt_ticket_id, irt_ticket_type,
            picklist_assigned_to, order_id, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (
            "WH-BLR-001", bin_label, fsn, irt_id, "INF",
            picker, order_id, now
        ))
    conn.commit()
    
    print(f"[repeat] {fsn} @ {bin_label} (order {order_id})")


def generate_inventory_adjust_event(conn, state: dict):
    """
    Inventory adjust: Update ATP/quantity for a seeded FSN, then create INF.
    
    Simulates inventory drift scenarios.
    """
    fsn = random.choice(SEEDED_FSNS)
    bin_label = random.choice(SEEDED_BINS)
    
    order_id = f"ORD-GEN-{state['order_seq']}"
    state['order_seq'] += 1
    
    irt_id = f"IRT-GEN-{state['tick']}-{random.randint(1000, 9999)}"
    picker = random.choice(["PKR-001", "PKR-002", "PKR-003"])
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update inventory (simulate ATP depletion)
    with conn.cursor() as cur:
        new_atp = random.choice([0, 0, 1, 2])
        new_qty = random.choice([0, 0, 1, 3])
        
        cur.execute("""
            UPDATE inventory_items
            SET atp = %s, quantity = %s, updated_at = %s
            WHERE warehouse_id = 'WH-BLR-001' AND fsn = %s
        """, (new_atp, new_qty, now, fsn))
        
        # Insert INF
        sql = """
        INSERT INTO pendency_mv (
            reservation_warehouse_id, picklist_source_location_label,
            picklist_item_fsn, irt_ticket_id, irt_ticket_type,
            picklist_assigned_to, order_id, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (
            "WH-BLR-001", bin_label, fsn, irt_id, "INF",
            picker, order_id, now
        ))
    conn.commit()
    
    print(f"[inventory_adjust] {fsn} atp={new_atp} qty={new_qty}, INF @ {bin_label}")


def generate_new_bin_event(conn, state: dict):
    """
    New bin: Create a new BIN with existing FSN + inbound context.
    
    Simulates expansion or putaway to new locations.
    """
    fsn = random.choice(SEEDED_FSNS)
    bin_label = f"BIN-GEN-{state['bin_seq']}"
    state['bin_seq'] += 1
    
    order_id = f"ORD-GEN-{state['order_seq']}"
    state['order_seq'] += 1
    
    irt_id = f"IRT-GEN-{state['tick']}-{random.randint(1000, 9999)}"
    picker = random.choice(["PKR-001", "PKR-002", "PKR-003"])
    grn_id = f"GRN-GEN-{state['bin_seq']}"
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with conn.cursor() as cur:
        # Insert inventory for new bin
        cur.execute("""
            INSERT INTO inventory_items (
                warehouse_id, fsn, atp, quantity, storage_location_label,
                flow, grn_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "WH-BLR-001", fsn, random.randint(0, 5), random.randint(0, 5),
            bin_label, "AVAILABLE", grn_id, now, now
        ))
        
        # Insert INF
        sql = """
        INSERT INTO pendency_mv (
            reservation_warehouse_id, picklist_source_location_label,
            picklist_item_fsn, irt_ticket_id, irt_ticket_type,
            picklist_assigned_to, order_id, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (
            "WH-BLR-001", bin_label, fsn, irt_id, "INF",
            picker, order_id, now
        ))
    conn.commit()
    
    print(f"[new_bin] {bin_label} created for {fsn}, INF logged")


def generate_new_fsn_event(conn, state: dict):
    """
    New FSN: Create new product with new BIN and INF.
    
    Every 3rd new FSN has no GRN (variance scenario).
    """
    fsn = f"FSN-GEN-{state['fsn_seq']}"
    state['fsn_seq'] += 1
    
    bin_label = f"BIN-GEN-{state['bin_seq']}"
    state['bin_seq'] += 1
    
    order_id = f"ORD-GEN-{state['order_seq']}"
    state['order_seq'] += 1
    
    irt_id = f"IRT-GEN-{state['tick']}-{random.randint(1000, 9999)}"
    picker = random.choice(["PKR-001", "PKR-002", "PKR-003"])
    
    # Every 3rd FSN has no GRN (variance)
    has_grn = (state['fsn_seq'] % 3) != 0
    grn_id = f"GRN-GEN-{state['fsn_seq']}" if has_grn else None
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with conn.cursor() as cur:
        # Insert inventory
        cur.execute("""
            INSERT INTO inventory_items (
                warehouse_id, fsn, atp, quantity, storage_location_label,
                flow, grn_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "WH-BLR-001", fsn, 0, 0 if not has_grn else random.randint(0, 3),
            bin_label, "AVAILABLE", grn_id, now, now
        ))
        
        # Insert INF
        sql = """
        INSERT INTO pendency_mv (
            reservation_warehouse_id, picklist_source_location_label,
            picklist_item_fsn, irt_ticket_id, irt_ticket_type,
            picklist_assigned_to, order_id, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cur.execute(sql, (
            "WH-BLR-001", bin_label, fsn, irt_id, "INF",
            picker, order_id, now
        ))
    conn.commit()
    
    variance_note = " (no GRN - variance)" if not has_grn else ""
    print(f"[new_fsn] {fsn} @ {bin_label}{variance_note}")


def generate_batch(state: dict):
    """Generate one batch of events."""
    conn = get_connection()
    try:
        # Pick next event type from rotation
        event_idx = state['tick'] % len(EVENTS)
        event_type = EVENTS[event_idx]
        
        if event_type == "repeat":
            generate_repeat_event(conn, state)
        elif event_type == "inventory_adjust":
            generate_inventory_adjust_event(conn, state)
        elif event_type == "new_bin":
            generate_new_bin_event(conn, state)
        elif event_type == "new_fsn":
            generate_new_fsn_event(conn, state)
        
        state['tick'] += 1
        state['last_event'] = event_type
        save_state(state)
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Continuous warehouse data generator")
    parser.add_argument("--once", action="store_true", help="Generate one batch and exit")
    parser.add_argument("--interval", type=int, default=2, help="Interval in seconds (default: 2)")
    parser.add_argument("--batches", type=int, help="Run N batches then exit")
    
    args = parser.parse_args()
    
    state = load_state()
    
    print(f"Data generator starting (tick={state['tick']})")
    print(f"Event rotation: {' → '.join(EVENTS)}")
    print(f"Interval: {args.interval}s")
    print()
    
    if args.once:
        generate_batch(state)
        print("Done (--once)")
        return
    
    batch_count = 0
    try:
        while True:
            generate_batch(state)
            batch_count += 1
            
            if args.batches and batch_count >= args.batches:
                print(f"Done ({args.batches} batches)")
                break
            
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    main()
