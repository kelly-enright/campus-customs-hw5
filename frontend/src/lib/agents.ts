/**
 * The five hands at the desk.
 *
 * Each agent gets its own colour, typeface and paper so the board can be read
 * at a glance without labels — Accounting's ledger green ruling never reads as
 * Customer Service's carbon-copy draft. The brief asked that agents "read
 * differently"; giving each one a stationery style rather than a coloured dot
 * is what makes a wall of events scannable.
 */

export type AgentKey = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export type AgentStyle = {
  key: AgentKey;
  name: string;
  role: string;
  /** What this agent is for, in the voice of a staff roster. */
  desk: string;
  color: string;
  /** CSS font stack var — each hand writes differently. */
  font: string;
  /** Paper the agent's notes are written on. */
  paper: string;
  /** Single glyph used as the agent's desk marker. */
  mark: string;
};

export const AGENTS: Record<AgentKey, AgentStyle> = {
  boss: {
    key: "boss",
    name: "Boss",
    role: "Floor",
    desk: "Reads the board, routes the work, settles disputes, closes tickets.",
    color: "var(--boss)",
    font: "var(--font-display)",
    paper: "#fffaf0",
    mark: "B",
  },
  inventory: {
    key: "inventory",
    name: "Inventory",
    role: "Stock",
    desk: "Counts by SKU and size, spots shortfalls, finds who can restock.",
    color: "var(--inventory)",
    font: "var(--font-condensed)",
    paper: "#f7f0dd",
    mark: "I",
  },
  accounting: {
    key: "accounting",
    name: "Accounting",
    role: "Ledger",
    desk: "Watches cash and invoices, checks margins, prepares payments.",
    color: "var(--accounting)",
    font: "var(--font-mono)",
    paper: "#eef5ee",
    mark: "A",
  },
  facilities: {
    key: "facilities",
    name: "Facilities",
    role: "Premises",
    desk: "Keeps the lease, the rent and the landlord in order.",
    color: "var(--facilities)",
    font: "var(--font-condensed)",
    paper: "#f3eef7",
    mark: "F",
  },
  customer_service: {
    key: "customer_service",
    name: "Customer Service",
    role: "Correspondence",
    desk: "Drafts letters to customers. Never sends — a person does that.",
    color: "var(--customer)",
    font: "var(--font-type)",
    paper: "#fbf3ec",
    mark: "C",
  },
};

export const AGENT_ORDER: AgentKey[] = [
  "boss", "inventory", "accounting", "facilities", "customer_service",
];

export const agentOf = (raw: string): AgentStyle =>
  AGENTS[(raw as AgentKey)] ?? {
    ...AGENTS.boss, key: "boss", name: raw, mark: raw.slice(0, 1).toUpperCase(),
  };

/** Plain-English gloss for an audit purpose, in desk language. */
export const purposeLabel = (p: string): string => ({
  run_started: "picked up the ticket",
  model_request: "thinking",
  model_text: "noted",
  tool_call: "looked something up",
  tool_cache_hit: "reused an answer",
  delegation_started: "asked a colleague",
  delegation_done: "reported back",
  delegation_refused: "refused — against the rules",
  delegation_timeout: "no answer in time",
  delegation_error: "could not reach them",
  budget_exhausted: "out of budget",
  agent_end: "finished",
  run_finished: "closed the run",
  run_error: "run failed",
  run_timeout: "run timed out",
}[p] ?? p.replace(/_/g, " "));
