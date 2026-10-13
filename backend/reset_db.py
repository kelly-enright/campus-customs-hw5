"""Reset the working database to the original shop values (shop rule 7).

    python backend/reset_db.py

Copies data/campus_customs.db over data/campus_customs_new.db, so every full
run starts from the same board: three open tickets, $3,400 in checking, no
payments, no approval queue. Without this, a second run inherits the first run's
decisions and the result is not reproducible.

The original is never written to. The audit trail is deliberately NOT touched —
it is append-only history across all runs (CC-OPS-31).
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "data" / "campus_customs.db"
WORKING = ROOT / "data" / "campus_customs_new.db"


def reset(verbose: bool = True) -> dict:
    if not ORIGINAL.exists():
        raise FileNotFoundError(f"Original database missing: {ORIGINAL}")
    shutil.copyfile(ORIGINAL, WORKING)

    conn = sqlite3.connect(WORKING)
    conn.row_factory = sqlite3.Row
    state = {
        "tickets": [dict(r) for r in conn.execute("SELECT id, status FROM tickets ORDER BY id")],
        "checking": conn.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0],
        "payments": conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
        "open_invoices": [dict(r) for r in conn.execute(
            "SELECT id, vendor_id, amount, status FROM invoices WHERE status='open'")],
        "pending_approvals": bool(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_approvals'"
        ).fetchone()),
    }
    conn.close()

    if verbose:
        print(f"reset {WORKING.name} from {ORIGINAL.name}")
        print(f"  tickets          {[(t['id'], t['status']) for t in state['tickets']]}")
        print(f"  checking         ${state['checking']:,.2f}")
        print(f"  payments         {state['payments']}")
        print(f"  open invoices    {[(i['id'], i['amount']) for i in state['open_invoices']]}")
        print(f"  approval queue   {'present' if state['pending_approvals'] else 'absent (fresh)'}")
    return state


if __name__ == "__main__":
    reset()
    sys.exit(0)
