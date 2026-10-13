"""Shared data types for the Campus Customs agent team.

Structured outputs keep the agents honest in a way prose cannot: a specialist
that must return a `Recommendation` has to name the rules it applied and the
tools it called, and Boss has to state a decision and what is waiting on a human
before the run can finish.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The five roles. Full connectivity means any of these may ask any other.
AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_NAMES: tuple[str, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)

AGENT_SCOPE: dict[str, str] = {
    "boss": "Reads the board, routes work, arbitrates between specialists, makes "
            "the final call, and is the only agent that closes a ticket.",
    "inventory": "Stock by SKU and size, shortfalls, par levels, restock quantities, "
                 "and which vendor can supply what by when.",
    "accounting": "Cash, invoices, margins, the discount ladder, and preparing "
                  "payments and purchase orders for human approval.",
    "facilities": "The shop space: leases, rent, landlords, due dates, and anything "
                  "that keeps the premises.",
    "customer_service": "Drafting messages to customers and requesters, in plain "
                        "language, promising only what the data supports.",
}


class Ticket(BaseModel):
    """One row of the ticket board."""

    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class Recommendation(BaseModel):
    """What a specialist hands back when another agent asks it something."""

    agent: str = Field(description="Which agent produced this.")
    answer: str = Field(description="The direct answer to the question asked.")
    facts_used: list[str] = Field(
        default_factory=list,
        description="Each concrete figure used, with the MCP tool it came from, "
                    "e.g. 'size S qty 0 (check_stock)'.",
    )
    rules_applied: list[str] = Field(
        default_factory=list, description="CC-OPS rule ids this answer relies on."
    )
    recommendation: str = Field(description="What the agent thinks should happen.")
    needs_human: bool = Field(
        default=False, description="True if this cannot proceed without a person."
    )
    confidence: Literal["high", "medium", "low"] = "medium"
    open_questions: list[str] = Field(
        default_factory=list,
        description="Anything the agent could not settle from the tools it has.",
    )


class PendingAction(BaseModel):
    """An action queued for a human, as Boss reports it."""

    approval_id: int | None = None
    kind: Literal["payment", "purchase_order", "customer_message"]
    summary: str
    amount: float | None = None
    prepared_by: str
    rule_ids: list[str] = Field(default_factory=list)
    why_human: str = Field(description="Which rule sent this to a person (CC-OPS-32).")


class BossDecision(BaseModel):
    """Boss's final output for one ticket."""

    ticket_id: int
    decision: str = Field(description="The call, in one or two sentences.")
    reasoning: str = Field(description="Why, citing the figures and rules behind it.")
    specialists_consulted: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
    pending_human_actions: list[PendingAction] = Field(default_factory=list)
    conflicts_surfaced: list[str] = Field(
        default_factory=list,
        description="Disagreements or cash conflicts raised to the human rather than "
                    "resolved by the team (CC-OPS-4, CC-OPS-24).",
    )
    ticket_closed: bool = False
    customer_message_drafted: bool = False


class Delegation(BaseModel):
    """One agent-to-agent hand-off, for the dashboard graph and the audit trail."""

    seq: int
    from_agent: str
    to_agent: str
    question: str
    depth: int
    status: Literal["running", "done", "refused", "error"] = "running"
    answer: str | None = None
    refusal_reason: str | None = None
    duration_ms: int | None = None


class AuditEntry(BaseModel):
    """One appended line of output/audit_trail.json (JSONL).

    Extends the schema HW 3 established for this shop so the two homeworks'
    trails can be read with the same tooling.
    """

    run_id: str
    ticket_id: int | None = None
    iteration: int
    timestamp: str
    agent: str
    purpose: str
    prompt_version: str
    model: str
    depth: int = 0
    parent_agent: str | None = None
    rules_checked: list[str] = Field(default_factory=list)
    thought_summary: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    result_summary: str | None = None
    processing_decision: str | None = None
    stop_reason: str | None = None
    duration_ms: int | None = None
    tokens: dict | None = None
    error: str | None = None


class TicketRunResult(BaseModel):
    """Everything one ticket run produced — returned to the API and dashboard."""

    run_id: str
    ticket_id: int
    model: str
    decision: BossDecision | None = None
    delegations: list[Delegation] = Field(default_factory=list)
    audit_entries: int = 0
    tool_calls: int = 0
    cache_hits: int = 0
    duration_ms: int = 0
    usage: dict = Field(default_factory=dict)
    limits_hit: list[str] = Field(default_factory=list)
    error: str | None = None
