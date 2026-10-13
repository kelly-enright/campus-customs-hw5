"""Run one ticket (or every open ticket) through the Campus Customs agent team.

    python backend/run_ticket.py 101
    python backend/run_ticket.py --all
    python backend/run_ticket.py --all --reset     # shop rule 7: clean board first

Appends to output/audit_trail.json; never truncates it.

Each ticket runs in its own child process under a hard wall-clock kill. The
in-process asyncio deadlines (CC-OPS-34) fire reliably at the delegation
boundary, but twice a run has sat at 0% CPU far past its budget with the await
stuck somewhere that does not honour cancellation. A deadline you can only
enforce from inside the thing you are timing is not a deadline — so the parent
holds the real one, and one wedged ticket no longer costs the whole board.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.team import run_ticket  # noqa: E402


def _print(result: dict) -> None:
    d = result.get("decision") or {}
    print(f"\n{'='*74}")
    print(f"TICKET {result['ticket_id']}   run {result['run_id']}   model {result['model']}")
    print("=" * 74)
    if result.get("error"):
        print("ERROR:", result["error"])
        return
    print(f"\nDECISION\n  {d.get('decision','')}")
    print(f"\nREASONING\n  {d.get('reasoning','')}")
    if d.get("specialists_consulted"):
        print(f"\nCONSULTED: {', '.join(d['specialists_consulted'])}")
    if d.get("rules_applied"):
        print(f"RULES:     {', '.join(d['rules_applied'])}")
    for p in d.get("pending_human_actions") or []:
        amt = f" ${p['amount']:,.2f}" if p.get("amount") else ""
        print(f"\nAWAITING HUMAN [{p['kind']}{amt}] by {p['prepared_by']}")
        print(f"  {p['summary']}")
        print(f"  why: {p['why_human']}")
    for c in d.get("conflicts_surfaced") or []:
        print(f"\nCONFLICT RAISED\n  {c}")
    print(f"\nticket_closed={d.get('ticket_closed')}  "
          f"message_drafted={d.get('customer_message_drafted')}")
    print(f"\nDELEGATIONS ({len(result['delegations'])}):")
    for g in result["delegations"]:
        mark = {"done": "ok", "refused": "refused", "error": "error"}.get(g["status"], g["status"])
        print(f"  {g['seq']}. {g['from_agent']} -> {g['to_agent']} (d{g['depth']}, {mark})")
        print(f"     q: {g['question'][:90]}")
        if g.get("refusal_reason"):
            print(f"     ! {g['refusal_reason']}")
    print(f"\naudit entries {result['audit_entries']} | tool calls {result['tool_calls']} "
          f"| cache hits {result.get('cache_hits', 0)} | {result['duration_ms']} ms")
    if result.get("limits_hit"):
        print("limits hit:", "; ".join(result["limits_hit"]))
    print("usage:", json.dumps(result.get("usage", {})))


HARD_KILL_S = 660.0  # parent-side wall clock, just past the 600s in-process budget


def _supervise(ticket_id: int, note: str) -> None:
    """Run one ticket in a child process we can actually kill."""
    cmd = [sys.executable, "-u", str(Path(__file__).resolve()), str(ticket_id), "--worker"]
    if note:
        cmd += ["--note", note]
    try:
        subprocess.run(cmd, timeout=HARD_KILL_S, check=False)
    except subprocess.TimeoutExpired:
        print(f"\n{'='*74}\nTICKET {ticket_id}  KILLED after {HARD_KILL_S:.0f}s\n{'='*74}")
        print("The in-process deadline did not fire — the run was wedged on a call that\n"
              "ignored cancellation. Parent killed it so the remaining tickets still run.\n"
              "Partial work is in output/audit_trail.json under this ticket's run id.")


async def main() -> None:
    ap = argparse.ArgumentParser(description="Run Campus Customs tickets through the agent team")
    ap.add_argument("ticket_id", nargs="?", type=int, help="Ticket id, e.g. 101")
    ap.add_argument("--all", action="store_true", help="Run every open ticket in order")
    ap.add_argument("--reset", action="store_true",
                    help="Reset the working database to original values first (shop rule 7)")
    ap.add_argument("--note", default="", help="Extra instruction from the owner")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    # The child does the actual work, in process, with no further supervision.
    if args.worker:
        _print(await run_ticket(args.ticket_id, args.note, args.run_id))
        return

    if args.reset:
        from reset_db import reset
        reset()
        print()

    if args.all:
        import sqlite3
        db = Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"
        ids = [r[0] for r in sqlite3.connect(db).execute(
            "SELECT id FROM tickets WHERE status='open' ORDER BY id")]
    elif args.ticket_id:
        ids = [args.ticket_id]
    else:
        ap.error("give a ticket id or --all")

    print(f"running {len(ids)} ticket(s): {ids}   hard kill {HARD_KILL_S:.0f}s each\n")
    for tid in ids:
        _supervise(tid, args.note)


if __name__ == "__main__":
    asyncio.run(main())
