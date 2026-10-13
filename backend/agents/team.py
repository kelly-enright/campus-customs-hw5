"""The Campus Customs agent team — five roles, fully connected.

Topology: every agent carries the same `ask_teammate` tool, so any agent may
delegate to any other. Boss is the entry point and the only agent that closes a
ticket, but it is not a bottleneck — Accounting can ask Inventory directly,
Customer Service can ask Facilities, and so on.

Shop facts come from one place: the MCP server in mcp_server/, loaded from the
same .mcp.json the vibe coder uses. There is no second tools layer. The only MCP
tool withheld from the agents is approve_pending, because that one moves money
and belongs to a human (CC-OPS-1).

Budget limits (CC-OPS-25..30) are enforced in code, not by asking the model
nicely. Delegations are capped and counted, depth is capped, repeat pairs are
refused, and an agent that burns its tool budget simply stops being offered
tools — it must answer from what it already gathered.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import load_mcp_toolsets
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.toolsets import WrapperToolset
from pydantic_ai.usage import UsageLimits

from agents import audit
from agents.config import (
    AGENT_TIMEOUT_S,
    MAX_REQUESTS_PER_AGENT,
    TICKET_TIMEOUT_S,
    MAX_DELEGATIONS,
    MAX_DEPTH,
    MAX_TOOL_CALLS_PER_AGENT,
    MCP_CONFIG_PATH,
    MODEL_NAME,
    PROMPTS_DIR,
    HUMAN_ONLY_TOOLS,
    build_model,
)
from models import AGENT_NAMES, AGENT_SCOPE, BossDecision, Delegation, Recommendation

SHOP_RULES = (PROMPTS_DIR / "shop_rules.md").read_text(encoding="utf-8")


def _roster() -> str:
    lines = [f"- **{name}** — {scope}" for name, scope in AGENT_SCOPE.items()]
    return (
        "## Your teammates\n\n"
        + "\n".join(lines)
        + "\n\nYou may ask any of them with `ask_teammate`, and they may ask each "
          "other. Ask a specific question; do not forward a whole ticket.\n"
    )


def _instructions(agent_name: str) -> str:
    role = (PROMPTS_DIR / f"{agent_name}.md").read_text(encoding="utf-8")
    return f"{role}\n\n---\n\n{_roster()}\n\n---\n\n{SHOP_RULES}"


PROMPT_VERSIONS = {name: audit.prompt_version(_instructions(name)) for name in AGENT_NAMES}


class CachingToolset(WrapperToolset):
    """Serve an identical MCP call from this run's cache instead of re-issuing it (CC-OPS-29).

    Shop facts do not change mid-run except through the prepare_* tools, so when
    Boss, Accounting and Inventory each ask for the cash position they should get
    one answer, not three round trips to the same rows. Measured on the first
    full run: every read tool was called three times per ticket.

    Write tools are never cached — queueing an approval twice must be two
    queued approvals, not a silently reused result.
    """

    WRITE_TOOLS = ("prepare_", "approve_", "close_")

    async def call_tool(self, name, tool_args, ctx, tool):
        deps = ctx.deps
        short = name.split("_", 1)[-1] if "_" in name else name
        if deps is None or any(w in name for w in self.WRITE_TOOLS):
            return await super().call_tool(name, tool_args, ctx, tool)

        key = (name, json.dumps(tool_args, sort_keys=True, default=str))
        if key in deps.tool_cache:
            deps.cache_hits += 1
            caller = getattr(getattr(ctx, "agent", None), "name", None) or "team"
            deps.log(caller, "tool_cache_hit",
                     tool_name=name, tool_args=_safe_args(tool_args),
                     rules_checked=["CC-OPS-29"],
                     result_summary=f"served from cache; {deps.cache_hits} hit(s) this run",
                     processing_decision="reuse cached result")
            return deps.tool_cache[key]

        result = await super().call_tool(name, tool_args, ctx, tool)
        deps.tool_cache[key] = result
        return result


@dataclass
class TeamDeps:
    """Per-ticket run state, shared by every agent in the run."""

    run_id: str
    ticket_id: int | None = None
    started: float = field(default_factory=time.perf_counter)
    iteration: int = 0
    delegations: list[Delegation] = field(default_factory=list)
    tool_calls: dict[str, int] = field(default_factory=dict)
    asked_pairs: set[tuple[str, str, str]] = field(default_factory=set)
    tool_cache: dict = field(default_factory=dict)
    cache_hits: int = 0
    limits_hit: list[str] = field(default_factory=list)
    audit_count: int = 0
    usage: dict = field(default_factory=dict)

    def next_iteration(self) -> int:
        self.iteration += 1
        return self.iteration

    def ms(self) -> int:
        return round((time.perf_counter() - self.started) * 1000)

    def tool_budget_left(self, agent_name: str) -> bool:
        return self.tool_calls.get(agent_name, 0) < MAX_TOOL_CALLS_PER_AGENT

    def note_limit(self, text: str) -> None:
        if text not in self.limits_hit:
            self.limits_hit.append(text)

    def log(self, agent: str, purpose: str, depth: int = 0, **extra: Any) -> None:
        """Append one agent-loop step to output/audit_trail.json (CC-OPS-31)."""
        entry = {
            "run_id": self.run_id,
            "ticket_id": self.ticket_id,
            "iteration": self.next_iteration(),
            "timestamp": audit.now_iso(),
            "agent": agent,
            "purpose": purpose,
            "prompt_version": PROMPT_VERSIONS.get(agent, ""),
            "model": MODEL_NAME,
            "depth": depth,
            "elapsed_ms": self.ms(),
            **extra,
        }
        audit.append(entry)
        self.audit_count += 1


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------

_AGENTS: dict[str, Agent] = {}


def _build_agent(name: str) -> Agent:
    output_type = BossDecision if name == "boss" else Recommendation
    agent = Agent(
        build_model(),
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=_instructions(name),
        name=name,
        retries=2,
    )

    @agent.tool
    async def ask_teammate(ctx: RunContext[TeamDeps], teammate: str, question: str) -> dict:
        """Ask another agent on the team a specific question in their domain.

        Args:
            teammate: One of boss, inventory, accounting, facilities, customer_service.
            question: A single specific question, with the concrete sku/size/ids it
                concerns. Do not forward a whole ticket — ask what you actually
                need to know.
        """
        return await _delegate(from_agent=name, teammate=teammate, question=question, ctx=ctx)

    return agent


def get_agent(name: str) -> Agent:
    if name not in _AGENTS:
        _AGENTS[name] = _build_agent(name)
    return _AGENTS[name]


def _toolset_for(agent_name: str, base_toolsets: list):
    """The MCP toolset as one agent sees it.

    Two filters: approve_pending is never offered to any agent (CC-OPS-1), and
    once an agent has spent its tool budget the MCP tools disappear entirely, so
    CC-OPS-28 is a real limit rather than a request.
    """

    def keep(ctx: RunContext[TeamDeps], tool_def) -> bool:
        short = tool_def.name.split("_")[-1] if "_" in tool_def.name else tool_def.name
        if any(tool_def.name.endswith(h) or short == h for h in HUMAN_ONLY_TOOLS):
            return False
        deps = ctx.deps
        if deps is not None and not deps.tool_budget_left(agent_name):
            deps.note_limit(f"CC-OPS-28: {agent_name} hit {MAX_TOOL_CALLS_PER_AGENT} tool calls")
            return False
        return True

    return [ts.filtered(keep) for ts in base_toolsets]


# --------------------------------------------------------------------------
# Delegation — the full-connectivity edge
# --------------------------------------------------------------------------

async def _delegate(from_agent: str, teammate: str, question: str,
                    ctx: RunContext[TeamDeps]) -> dict:
    deps = ctx.deps
    depth = _depth_of(from_agent, deps) + 1
    seq = len(deps.delegations) + 1

    def refuse(reason: str, rule: str) -> dict:
        deps.note_limit(f"{rule}: {reason}")
        deps.delegations.append(Delegation(
            seq=seq, from_agent=from_agent, to_agent=teammate, question=question,
            depth=depth, status="refused", refusal_reason=reason,
        ))
        deps.log(from_agent, "delegation_refused", depth=depth,
                 tool_name="ask_teammate", tool_args={"teammate": teammate, "question": question},
                 rules_checked=[rule], result_summary=reason,
                 processing_decision="refused", stop_reason=rule)
        return {"status": "refused", "reason": reason, "rule": rule,
                "guidance": "Answer from what you already have and name the open question."}

    if teammate not in AGENT_NAMES:
        return refuse(f"'{teammate}' is not on the team; pick one of {', '.join(AGENT_NAMES)}.",
                      "CC-OPS-22")
    if teammate == from_agent:
        return refuse("An agent may not delegate to itself.", "CC-OPS-27")
    if len(deps.delegations) >= MAX_DELEGATIONS:
        return refuse(f"Delegation budget of {MAX_DELEGATIONS} for this ticket is spent.",
                      "CC-OPS-25")
    if depth > MAX_DEPTH:
        return refuse(f"Delegation depth {depth} exceeds the limit of {MAX_DEPTH}.", "CC-OPS-26")

    key = (from_agent, teammate, question.strip().lower()[:120])
    if key in deps.asked_pairs:
        return refuse(f"{from_agent} already asked {teammate} this on this ticket.", "CC-OPS-27")
    if _would_cycle(from_agent, teammate, deps):
        return refuse(f"{teammate} is already waiting on {from_agent} in this chain.", "CC-OPS-27")
    deps.asked_pairs.add(key)

    record = Delegation(seq=seq, from_agent=from_agent, to_agent=teammate,
                        question=question, depth=depth, status="running")
    deps.delegations.append(record)
    deps.log(from_agent, "delegation_started", depth=depth, tool_name="ask_teammate",
             tool_args={"teammate": teammate, "question": audit.clip(question)},
             rules_checked=["CC-OPS-22"], processing_decision=f"delegate to {teammate}")

    started = time.perf_counter()
    try:
        result = await _run_agent(teammate, question, deps, depth=depth, parent=from_agent)
        out = result.output
        record.status = "done"
        record.answer = out.answer if isinstance(out, Recommendation) else str(out)
        record.duration_ms = round((time.perf_counter() - started) * 1000)
        payload = out.model_dump() if hasattr(out, "model_dump") else {"answer": str(out)}
        deps.log(teammate, "delegation_done", depth=depth, parent_agent=from_agent,
                 result_summary=audit.clip(record.answer),
                 rules_checked=getattr(out, "rules_applied", []) or [],
                 duration_ms=record.duration_ms, processing_decision="answered")
        return {"status": "ok", "from": teammate, **payload}
    except (TimeoutError, asyncio.TimeoutError) as exc:
        record.status = "error"
        record.refusal_reason = f"{teammate} timed out (CC-OPS-34)"
        record.duration_ms = round((time.perf_counter() - started) * 1000)
        deps.note_limit(f"CC-OPS-34: {teammate} timed out")
        deps.log(teammate, "delegation_timeout", depth=depth, parent_agent=from_agent,
                 error=str(exc) or "timeout", stop_reason="timeout",
                 duration_ms=record.duration_ms)
        return {"status": "error", "reason": record.refusal_reason,
                "guidance": "Proceed without this answer and say it is missing."}
    except Exception as exc:  # noqa: BLE001 — surfaced to the asking agent, not swallowed
        record.status = "error"
        record.refusal_reason = str(exc)
        record.duration_ms = round((time.perf_counter() - started) * 1000)
        deps.log(teammate, "delegation_error", depth=depth, parent_agent=from_agent,
                 error=str(exc), stop_reason="exception", duration_ms=record.duration_ms)
        return {"status": "error", "reason": str(exc),
                "guidance": "Proceed without this answer and say it is missing."}


def _depth_of(agent_name: str, deps: TeamDeps) -> int:
    for d in reversed(deps.delegations):
        if d.to_agent == agent_name and d.status == "running":
            return d.depth
    return 0


def _would_cycle(from_agent: str, teammate: str, deps: TeamDeps) -> bool:
    """True if teammate is already somewhere up this still-running chain."""
    chain, cursor = set(), from_agent
    for _ in range(MAX_DEPTH + 1):
        parent = next(
            (d.from_agent for d in reversed(deps.delegations)
             if d.to_agent == cursor and d.status == "running"), None
        )
        if parent is None:
            break
        chain.add(parent)
        cursor = parent
    return teammate in chain or teammate == from_agent


# --------------------------------------------------------------------------
# Running one agent, auditing every loop step
# --------------------------------------------------------------------------

_BASE_TOOLSETS: list = []


async def _run_agent(agent_name: str, prompt: str, deps: TeamDeps,
                     depth: int = 0, parent: str | None = None):
    """Run one agent's loop, appending an audit entry per graph node."""
    agent = get_agent(agent_name)
    toolsets = _toolset_for(agent_name, _BASE_TOOLSETS)
    # CC-OPS-33/34: cap model round-trips and tool calls, and never let one
    # unanswered request hang the ticket.
    # Only request_limit here. CC-OPS-28 is enforced by the toolset filter
    # instead, because a UsageLimits tool cap aborts the run with an exception
    # while the filter simply stops offering tools — the agent then answers from
    # what it has, which is the behaviour the rule actually wants.
    limits = UsageLimits(request_limit=MAX_REQUESTS_PER_AGENT)
    # An agent's clock has to contain every agent it delegates to, so the budget
    # halves with depth rather than being flat: Boss owns the whole ticket
    # window, a depth-3 specialist owns the floor. A flat cap times Boss out
    # while it is only waiting on the specialists it correctly asked.
    budget = max(AGENT_TIMEOUT_S, TICKET_TIMEOUT_S / (2 ** depth))

    try:
      async with asyncio.timeout(budget):
       async with agent.iter(prompt, deps=deps, toolsets=toolsets, usage_limits=limits) as run:
        async for node in run:
            kind = type(node).__name__
            if kind == "ModelRequestNode":
                deps.log(agent_name, "model_request", depth=depth, parent_agent=parent,
                         thought_summary="sending context to the model",
                         processing_decision="call_model")
            elif kind == "CallToolsNode":
                parts = getattr(getattr(node, "model_response", None), "parts", []) or []
                calls = [p for p in parts if type(p).__name__ == "ToolCallPart"]
                texts = [getattr(p, "content", "") for p in parts
                         if type(p).__name__ == "TextPart"]
                for call in calls:
                    tool_name = getattr(call, "tool_name", "?")
                    short = tool_name.split("_")[-1]
                    # ask_teammate is capped by CC-OPS-25 and final_result is the
                    # structured-output call, so neither spends the MCP budget.
                    if tool_name not in ("ask_teammate", "final_result"):
                        deps.tool_calls[agent_name] = deps.tool_calls.get(agent_name, 0) + 1
                    deps.log(agent_name, "tool_call", depth=depth, parent_agent=parent,
                             tool_name=tool_name,
                             tool_args=_safe_args(getattr(call, "args", None)),
                             thought_summary=audit.clip(" ".join(texts)) if texts else None,
                             processing_decision=f"call {short}",
                             result_summary=f"tool call {deps.tool_calls[agent_name]}"
                                            f"/{MAX_TOOL_CALLS_PER_AGENT} for {agent_name}")
                if not calls and texts:
                    deps.log(agent_name, "model_text", depth=depth, parent_agent=parent,
                             thought_summary=audit.clip(" ".join(texts)),
                             processing_decision="no tool call")
            elif kind == "End":
                deps.log(agent_name, "agent_end", depth=depth, parent_agent=parent,
                         stop_reason="completed", processing_decision="return output")

        result = run.result
    except UsageLimitExceeded as exc:
        deps.note_limit(f"CC-OPS-33: {agent_name} hit {MAX_REQUESTS_PER_AGENT} model requests")
        deps.log(agent_name, "budget_exhausted", depth=depth, parent_agent=parent,
                 error=str(exc), stop_reason="usage_limit",
                 processing_decision="return partial answer")
        return _partial(agent_name, deps, f"Stopped at the CC-OPS-33 budget: {exc}")

    try:
        u = result.usage()
        deps.usage[agent_name] = {
            "requests": getattr(u, "requests", None),
            "input_tokens": getattr(u, "input_tokens", None),
            "output_tokens": getattr(u, "output_tokens", None),
        }
    except Exception:  # noqa: BLE001 — usage is nice to have, never load-bearing
        pass
    return result


class _Partial:
    """Stands in for a run result when an agent stopped at a budget limit."""

    def __init__(self, output): self.output = output
    def usage(self): raise RuntimeError("no usage for a partial run")


def _partial(agent_name: str, deps: TeamDeps, reason: str):
    """A usable answer when an agent runs out of budget mid-loop.

    Returning something structured beats raising: the agent that asked gets a
    clear 'this is incomplete and here is why' instead of an exception, which is
    what CC-OPS-4 asks for — surface the gap, never silently drop it.
    """
    facts = [f"{k}: {v} tool calls" for k, v in deps.tool_calls.items()]
    if agent_name == "boss":
        return _Partial(BossDecision(
            ticket_id=deps.ticket_id or 0,
            decision="Stopped before deciding — budget limit reached.",
            reasoning=reason,
            specialists_consulted=sorted({d.to_agent for d in deps.delegations}),
            rules_applied=["CC-OPS-33"],
            conflicts_surfaced=[reason],
            ticket_closed=False,
        ))
    return _Partial(Recommendation(
        agent=agent_name,
        answer=f"Incomplete: {reason}",
        facts_used=facts,
        rules_applied=["CC-OPS-33"],
        recommendation="Treat this as missing and proceed without it.",
        needs_human=True,
        confidence="low",
        open_questions=[reason],
    ))


def _safe_args(args: Any) -> dict | None:
    if args is None:
        return None
    if isinstance(args, dict):
        return {k: audit.clip(v, 200) if isinstance(v, str) else v for k, v in args.items()}
    return {"raw": audit.clip(args, 200)}


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

async def run_ticket(ticket_id: int, extra_instruction: str = "",
                     run_id: str | None = None) -> dict:
    """Work one ticket end to end, starting with Boss. Returns a TicketRunResult dict."""
    from models import TicketRunResult  # local import keeps module import cheap

    run_id = run_id or uuid.uuid4().hex[:12]
    deps = TeamDeps(run_id=run_id, ticket_id=ticket_id)
    started = time.perf_counter()

    prompt = (
        f"Work ticket {ticket_id}. Read it first with list_open_tickets, then decide "
        f"what it needs and who should help. Finish with a decision, anything queued "
        f"for a human, and close the ticket only if nothing is pending on it."
    )
    if extra_instruction:
        prompt += f"\n\nAdditional instruction from the owner: {extra_instruction}"

    deps.log("boss", "run_started", rules_checked=["CC-OPS-31"],
             thought_summary=f"ticket {ticket_id} picked up",
             processing_decision="start", result_summary=audit.clip(prompt))

    global _BASE_TOOLSETS
    error = None
    decision = None
    async with AsyncExitStack() as stack:
        loaded = load_mcp_toolsets(MCP_CONFIG_PATH)
        for ts in loaded:
            await stack.enter_async_context(ts)
        # CC-OPS-29: one cache shared by every agent for the length of this run.
        _BASE_TOOLSETS = [CachingToolset(ts) for ts in loaded]
        try:
            async with asyncio.timeout(TICKET_TIMEOUT_S):
                result = await _run_agent("boss", prompt, deps, depth=0)
            decision = result.output
        except (TimeoutError, asyncio.TimeoutError):
            error = (f"ticket run hit a CC-OPS-34 deadline "
                     f"(boss budget {TICKET_TIMEOUT_S:.0f}s)")
            deps.note_limit(error)
            deps.log("boss", "run_timeout", error=error, stop_reason="timeout")
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            deps.log("boss", "run_error", error=error, stop_reason="exception")

    duration = round((time.perf_counter() - started) * 1000)
    deps.log("boss", "run_finished", stop_reason="done" if error is None else "error",
             duration_ms=duration,
             result_summary=audit.clip(decision.decision if decision else (error or "")),
             processing_decision="finish")

    out = TicketRunResult(
        run_id=run_id,
        ticket_id=ticket_id,
        model=MODEL_NAME,
        decision=decision if isinstance(decision, BossDecision) else None,
        delegations=deps.delegations,
        audit_entries=deps.audit_count,
        tool_calls=sum(deps.tool_calls.values()),
        cache_hits=deps.cache_hits,
        duration_ms=duration,
        usage=deps.usage,
        limits_hit=deps.limits_hit,
        error=error,
    )
    return out.model_dump()
