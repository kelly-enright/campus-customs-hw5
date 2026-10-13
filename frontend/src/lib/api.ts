/**
 * Client for the Campus Customs backend (Problem 7), running on :8000.
 *
 * Everything the desk knows comes from here. No shop facts are computed in the
 * browser — if a number appears on screen it came from the API, which got it
 * from the MCP server, which read the database. One chain, one truth.
 */

export const API = "http://localhost:8000";

/* ---------- shapes the backend returns ---------- */

export type Ticket = {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  is_open: boolean;
  pending_approvals: number;
};

export type AgentEvent = {
  index: number;
  run_id: string;
  ticket_id: number | null;
  iteration: number;
  timestamp: string;
  agent: string;
  purpose: string;
  said: string | null;
  tool: string | null;
  tool_args: Record<string, unknown> | null;
  result: string | null;
  decision: string | null;
  rules: string[];
  depth: number;
  parent: string | null;
  stop_reason: string | null;
  error: string | null;
  elapsed_ms: number | null;
};

export type Approval = {
  id: number;
  ticket_id: number | null;
  kind: "payment" | "purchase_order" | "customer_message";
  summary: string;
  payload: Record<string, any>;
  amount: number | null;
  rule_ids: string | null;
  reason: string | null;
  prepared_by: string;
  prepared_at: string;
  status: string;
  decided_by: string | null;
};

export type Obligation = {
  priority: number;
  kind: string;
  label: string;
  amount: number;
  due: string;
  is_overdue: boolean;
  balance_after?: number;
  balance_after_if_paid?: number;
  blocked_by?: string;
};

export type Cash = {
  checking_balance: number | null;
  as_of: string | null;
  shop_today: string | null;
  cash_floor: number | null;
  spendable_above_floor: number | null;
  total_obligations: number | null;
  can_fund_everything: boolean | null;
  escalation_required: boolean | null;
  outflow_only: boolean | null;
  obligations: Obligation[];
  blocked_by_floor: Obligation[];
};

/* ---------- transport ---------- */

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly detail?: unknown) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      "Can't reach the backend. Start it with: uvicorn main:app --reload --port 8000",
      0,
    );
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (body as any)?.detail;
    // A 409 is the shop's rules declining, not a crash — the desk shows it as
    // an explanation rather than an error, so keep the structured detail.
    const msg =
      typeof detail === "string"
        ? detail
        : detail?.reason ?? `Request failed (${res.status})`;
    throw new ApiError(msg, res.status, detail);
  }
  return body as T;
}

/* ---------- routes ---------- */

export const getTickets = () =>
  req<{ shop_today: string; count: number; open_count: number; tickets: Ticket[] }>("/tickets");

export const runTicket = (id: number, note = "") =>
  req<{ run_id: string; ticket_id: number; status: string; model: string }>(
    `/tickets/${id}/run`,
    { method: "POST", body: JSON.stringify({ note }) },
  );

export const getEvents = (runId: string, since = 0) =>
  req<{ total: number; returned: number; next_since: number; run_finished: boolean; events: AgentEvent[] }>(
    `/events?run_id=${encodeURIComponent(runId)}&since=${since}&limit=400`,
  );

/** Every event recorded for a ticket, across all its runs. */
export const getTicketEvents = (ticketId: number) =>
  req<{ total: number; returned: number; next_since: number; run_finished: boolean; events: AgentEvent[] }>(
    `/events?ticket_id=${ticketId}&since=0&limit=2000`,
  );

export const getApprovals = (status = "pending") =>
  req<{ count: number; total_amount: number; approvals: Approval[] }>(
    `/approvals?status=${status}`,
  );

export const decideApproval = (id: number, approved_by: string, decision: "approve" | "reject", note?: string) =>
  req<any>(`/approvals/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ approved_by, decision, note }),
  });

export const getCash = () => req<Cash>("/cash");

export const resetDb = () => req<any>("/reset", { method: "POST" });

export const getHealth = () =>
  req<{ ok: boolean; model: string; mcp: string; shop_today: string }>("/health");
