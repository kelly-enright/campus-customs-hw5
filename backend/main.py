"""FastAPI backend for the Campus Customs dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Docs at http://localhost:8000/docs

Two design rules this file keeps:

1. **Shop facts and shop changes go through MCP.** Routes call the MCP server in
   mcp_server/ rather than opening the database, so the dashboard, the agents and
   the vibe coder all see one definition of the shop and one place where the rules
   are enforced. The only exception is /reset, which is a file operation on the
   database rather than a fact about the shop.
2. **Only this layer can move money.** The agents' toolset has approve_pending
   filtered out (CC-OPS-1); POST /approvals/{id}/decision is where a human's click
   becomes a cash movement, and it records that person's name.

A ticket run takes one to five minutes of live model calls, so POST /tickets/{id}/run
does not block. It spawns the same supervised worker the CLI uses, returns a run_id
immediately, and the dashboard follows progress through /events. A dashboard that
hangs for four minutes on a request is not a dashboard.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from agents import audit  # noqa: E402
from agents.config import AUDIT_PATH, MCP_CONFIG_PATH, MODEL_NAME  # noqa: E402
from reset_db import reset as reset_database  # noqa: E402

RUN_TIMEOUT_S = 660.0  # same hard kill the CLI uses

# In-memory record of runs started this process. The durable record is the audit
# trail; this is only so the dashboard can poll a run it just started.
RUNS: dict[str, dict] = {}


# --------------------------------------------------------------------------
# MCP plumbing
# --------------------------------------------------------------------------

async def mcp_call(tool: str, args: dict | None = None) -> Any:
    """Call one MCP tool and return its structured result.

    A fresh client per call keeps this stateless and avoids a long-lived
    subprocess wedging the API — the cost is a process spawn, which is
    negligible next to anything else happening here.
    """
    from fastmcp import Client

    # Pass the parsed config, not the path — fastmcp cannot infer a transport
    # from a bare filename. Same .mcp.json the agents and the vibe coder use.
    config = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    try:
        async with Client(config) as client:
            # A single-server .mcp.json exposes tools unprefixed.
            result = await client.call_tool(tool, args or {})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"MCP call '{tool}' failed: {exc}") from exc
    data = getattr(result, "structured_content", None)
    if data is None:
        data = getattr(result, "data", None)
    return data


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

class RunRequest(BaseModel):
    note: str = Field("", description="Optional extra instruction from the owner.")


class RunStarted(BaseModel):
    run_id: str
    ticket_id: int
    status: str
    model: str
    poll: str


class Decision(BaseModel):
    approved_by: str = Field(..., min_length=1,
                             description="The person deciding. Never an agent name.")
    decision: Literal["approve", "reject"] = "approve"
    note: str | None = None


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for run in RUNS.values():
        proc = run.pop("_proc", None)
        if proc and proc.returncode is None:
            proc.kill()


app = FastAPI(
    title="Campus Customs Operations API",
    description="Backend for the Campus Customs agent dashboard. "
                "Agents prepare; humans approve; only this API moves money.",
    version="1.0.0",
    lifespan=lifespan,
)

# The dashboard runs on a different origin in dev (Vite on 5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
async def root() -> dict:
    """What this API is and where everything lives."""
    return {
        "service": "Campus Customs Operations API",
        "model": MODEL_NAME,
        "docs": "/docs",
        "routes": {
            "GET /tickets": "the board — every ticket and whether it is open or resolved",
            "POST /tickets/{id}/run": "run the agent team on one ticket (returns immediately)",
            "GET /events": "recent agent events — who said what, which tools they used",
            "GET /approvals": "what agents have queued for a human to decide",
            "POST /approvals/{id}/decision": "approve or reject — the only route that moves cash",
            "GET /cash": "current checking balance and what is claimed against it",
            "POST /reset": "reset the database to original values for a fresh run",
        },
    }


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness plus a real MCP round trip, so a green check means the chain works."""
    tickets = await mcp_call("list_open_tickets", {"status": "all"})
    return {
        "ok": True,
        "model": MODEL_NAME,
        "mcp": "connected",
        "tickets_visible": tickets.get("count", 0),
        "shop_today": tickets.get("shop_today"),
    }


# ---- (a) the board ----------------------------------------------------------

@app.get("/tickets", tags=["board"])
async def get_tickets(status: str = Query("all", description="all | open | resolved")) -> dict:
    """Every ticket on the board with its status, plus what is pending on each.

    The dashboard needs resolved tickets too, not just open ones, so a run that
    closes something is visibly different from one that could not.
    """
    data = await mcp_call("list_open_tickets", {"status": status})
    pending = await mcp_call("list_pending_approvals", {"status": "pending"})
    by_ticket: dict[int, int] = {}
    for a in (pending or {}).get("approvals", []):
        if a.get("ticket_id") is not None:
            by_ticket[a["ticket_id"]] = by_ticket.get(a["ticket_id"], 0) + 1

    tickets = []
    for t in (data or {}).get("tickets", []):
        tickets.append({**t,
                        "is_open": t.get("status") == "open",
                        "pending_approvals": by_ticket.get(t.get("id"), 0)})
    return {
        "shop_today": data.get("shop_today"),
        "count": len(tickets),
        "open_count": sum(1 for t in tickets if t["is_open"]),
        "tickets": tickets,
    }


@app.get("/tickets/{ticket_id}", tags=["board"])
async def get_ticket(ticket_id: int) -> dict:
    """One ticket in full."""
    data = await mcp_call("list_open_tickets", {"ticket_id": ticket_id})
    if not (data or {}).get("found"):
        raise HTTPException(404, (data or {}).get("reason", f"No ticket {ticket_id}."))
    return data


# ---- (b) run the agent team -------------------------------------------------

@app.post("/tickets/{ticket_id}/run", response_model=RunStarted, tags=["agents"])
async def run_ticket_route(ticket_id: int, body: RunRequest | None = None) -> RunStarted:
    """Start the agent team on one ticket. Returns immediately with a run_id.

    The run takes minutes of live model calls, so it is spawned as the same
    supervised worker process the CLI uses — hard-killed at 660s if it wedges,
    which it cannot do from inside the API. Follow it with
    GET /events?run_id=... until an event with purpose 'run_finished' appears.
    """
    ticket = await mcp_call("list_open_tickets", {"ticket_id": ticket_id})
    if not (ticket or {}).get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")

    active = [r for r in RUNS.values()
              if r["ticket_id"] == ticket_id and r["status"] == "running"]
    if active:
        raise HTTPException(409, f"Ticket {ticket_id} is already running as "
                                 f"{active[0]['run_id']}.")

    run_id = uuid.uuid4().hex[:12]
    cmd = [sys.executable, "-u", str(HERE / "run_ticket.py"), str(ticket_id),
           "--worker", "--run-id", run_id]
    if body and body.note:
        cmd += ["--note", body.note]

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(ROOT),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "_proc": proc}

    async def _supervise() -> None:
        record = RUNS[run_id]
        try:
            await asyncio.wait_for(proc.wait(), timeout=RUN_TIMEOUT_S)
            record["status"] = "finished" if proc.returncode == 0 else "error"
            record["exit_code"] = proc.returncode
        except asyncio.TimeoutError:
            proc.kill()
            record["status"] = "killed"
            record["error"] = f"exceeded {RUN_TIMEOUT_S:.0f}s and was killed"
        finally:
            record.pop("_proc", None)
            record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    asyncio.create_task(_supervise())
    return RunStarted(run_id=run_id, ticket_id=ticket_id, status="running",
                      model=MODEL_NAME, poll=f"/events?run_id={run_id}")


@app.get("/runs", tags=["agents"])
async def list_runs() -> dict:
    """Runs started by this server process, newest first."""
    runs = [{k: v for k, v in r.items() if not k.startswith("_")} for r in RUNS.values()]
    return {"count": len(runs), "runs": sorted(runs, key=lambda r: r["started_at"], reverse=True)}


@app.get("/runs/{run_id}", tags=["agents"])
async def get_run(run_id: str) -> dict:
    """One run's status, with a live count of what it has logged so far."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} in this process.")
    record = {k: v for k, v in RUNS[run_id].items() if not k.startswith("_")}
    entries = [e for e in audit.read_all(AUDIT_PATH) if e.get("run_id") == run_id]
    record["audit_entries"] = len(entries)
    record["last_event"] = entries[-1] if entries else None
    return record


# ---- (c) recent agent events ------------------------------------------------

@app.get("/events", tags=["agents"])
async def get_events(
    run_id: str | None = Query(None, description="Only this run"),
    ticket_id: int | None = Query(None, description="Only this ticket"),
    since: int = Query(0, ge=0, description="Return events after this index — poll with it"),
    limit: int = Query(200, ge=1, le=2000),
) -> dict:
    """Recent agent events: who acted, what they said, which tools they called.

    Reads the append-only audit trail, so it covers runs this process did not
    start. Poll with `since` set to the `next_since` from the previous call to
    get only what is new, rather than re-sending the whole trail each refresh.
    """
    entries = audit.read_all(AUDIT_PATH)
    if run_id:
        entries = [e for e in entries if e.get("run_id") == run_id]
    if ticket_id is not None:
        entries = [e for e in entries if e.get("ticket_id") == ticket_id]

    total = len(entries)
    window = entries[since:since + limit]
    events = [{
        "index": since + i,
        "run_id": e.get("run_id"),
        "ticket_id": e.get("ticket_id"),
        "iteration": e.get("iteration"),
        "timestamp": e.get("timestamp"),
        "agent": e.get("agent"),
        "purpose": e.get("purpose"),
        "said": e.get("thought_summary"),
        "tool": (e.get("tool_name") or "").replace("campus-customs-ops_", "") or None,
        "tool_args": e.get("tool_args"),
        "result": e.get("result_summary"),
        "decision": e.get("processing_decision"),
        "rules": e.get("rules_checked") or [],
        "depth": e.get("depth", 0),
        "parent": e.get("parent_agent"),
        "stop_reason": e.get("stop_reason"),
        "error": e.get("error"),
        "elapsed_ms": e.get("elapsed_ms"),
    } for i, e in enumerate(window)]

    finished = any(e["purpose"] in ("run_finished", "run_error", "run_timeout") for e in events)
    return {"total": total, "returned": len(events), "next_since": since + len(events),
            "run_finished": finished, "events": events}


# ---- (d/e) human approval — the only route that moves money -----------------

@app.get("/approvals", tags=["approvals"])
async def get_approvals(status: str = Query("pending", description="pending | approved | rejected | all")) -> dict:
    """What agents have queued for a human to decide.

    Agents only ever prepare (CC-OPS-1); everything they propose waits here with
    the rule that sent it, so the person deciding can see what they are overriding.
    """
    data = await mcp_call("list_pending_approvals", {"status": status})
    approvals = (data or {}).get("approvals", [])
    return {
        "count": len(approvals),
        "status_filter": status,
        "total_amount": round(sum(a.get("amount") or 0 for a in approvals), 2),
        "approvals": approvals,
    }


@app.post("/approvals/{approval_id}/decision", tags=["approvals"])
async def decide_approval(approval_id: int, body: Decision) -> dict:
    """Approve or reject a queued action. **This is the route that changes cash.**

    Agents prepare payments and purchase orders but can never execute them — the
    MCP tool behind this route is filtered out of every agent's toolset. Here a
    person's name is recorded against the movement.

    The server re-checks the reserve floor and the zero-balance rule at execution
    time, because the balance can have moved since the action was queued. A refusal
    here is the guardrail working, not an error to route around.
    """
    if not body.approved_by.strip():
        raise HTTPException(400, "approved_by must name a real person (CC-OPS-1).")

    result = await mcp_call("approve_pending", {
        "approval_id": approval_id,
        "approved_by": body.approved_by.strip(),
        "decision": body.decision,
        "note": body.note,
    })
    if not (result or {}).get("ok"):
        # 409: the request was well formed, the shop's rules refused it.
        raise HTTPException(409, {"refused": True, **(result or {})})
    cash = await mcp_call("get_cash_position")
    return {**result, "cash_now": (cash or {}).get("total_cash")}


# ---- (f) cash ---------------------------------------------------------------

@app.get("/cash", tags=["cash"])
async def get_cash() -> dict:
    """Current checking balance, and every claim competing for it.

    The bare balance is misleading on its own — this board's whole problem is
    that $3,400 looks like plenty until you line up what is owed against it.
    """
    data = await mcp_call("get_cash_position")
    accounts = (data or {}).get("cash_accounts", [])
    checking = next((a for a in accounts if a.get("name") == "checking"), None)
    return {
        "checking_balance": (checking or {}).get("balance"),
        "as_of": (checking or {}).get("date"),
        "shop_today": data.get("shop_today"),
        "cash_floor": data.get("cash_floor_cc_ops_2"),
        "spendable_above_floor": data.get("spendable_above_floor"),
        "total_obligations": data.get("total_obligations"),
        "can_fund_everything": data.get("can_fund_everything"),
        "escalation_required": data.get("escalation_required_cc_ops_4"),
        "outflow_only": data.get("cash_is_outflow_only_cc_ops_36"),
        "obligations": data.get("obligations_in_priority_order_cc_ops_3", []),
        "blocked_by_floor": data.get("blocked_by_floor", []),
        "accounts": accounts,
    }


# ---- (g) reset --------------------------------------------------------------

@app.post("/reset", tags=["admin"])
async def reset_route() -> dict:
    """Reset the working database to the original shop values for a fresh run.

    Copies data/campus_customs.db over the working copy: three open tickets,
    $3,400 in checking, no payments, no approval queue. The audit trail is
    deliberately left alone — it is append-only history across all runs
    (CC-OPS-31), and wiping it would destroy the record of what was reset.
    """
    active = [r["run_id"] for r in RUNS.values() if r["status"] == "running"]
    if active:
        raise HTTPException(409, f"Cannot reset while runs are in flight: {active}")
    state = reset_database(verbose=False)
    return {"ok": True, "reset_to": "data/campus_customs.db",
            "audit_trail": "left intact (append-only, CC-OPS-31)", "state": state}
