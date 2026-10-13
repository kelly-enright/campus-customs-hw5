import { AGENTS, AGENT_ORDER, agentOf } from "../lib/agents";
import type { AgentEvent } from "../lib/api";

/**
 * The end-of-run docket: one short paragraph per agent in that agent's own hand,
 * plus the guardrails that fired.
 *
 * This answers "what did each agent actually do on this ticket" without making
 * anyone scroll the wire. The guardrail strip is the part worth staring at — a
 * refused cycle or an absorbed timeout is the system holding, and if the desk
 * does not show it, nobody ever sees the safety work happen.
 */
export default function RunSummary({ events }: { events: AgentEvent[] }) {
  const finish = events.find(e => ["run_finished", "run_error", "run_timeout"].includes(e.purpose));
  if (!finish) return null;

  const perAgent = summarise(events);
  const guards = events.filter(e =>
    e.purpose === "delegation_refused" || e.purpose === "delegation_timeout" ||
    e.purpose === "budget_exhausted");
  const tools = events.filter(e => e.purpose === "tool_call" &&
    e.tool && !["ask_teammate", "final_result"].includes(e.tool)).length;
  const cached = events.filter(e => e.purpose === "tool_cache_hit").length;
  const seconds = ((finish.elapsed_ms ?? 0) / 1000).toFixed(0);
  const failed = finish.purpose !== "run_finished" || !!finish.error;

  return (
    <section aria-label="Run summary" className="sheet drop-in" style={{ padding: "16px 18px 18px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: 18 }}>THE&nbsp;DOCKET</h2>
        <span className={`stamp ${failed ? "refused" : "resolved"} stamp-in`}>
          {failed ? "Run failed" : "Run complete"}
        </span>
      </div>
      <hr className="rule" style={{ marginTop: 10 }} />

      {/* what the Boss concluded */}
      {finish.result && (
        <blockquote style={{
          margin: "0 0 15px", padding: "11px 14px",
          borderLeft: "4px solid var(--crimson)", background: "rgba(150,48,31,.05)",
          fontSize: 14.5, lineHeight: 1.55,
        }}>
          {finish.result}
        </blockquote>
      )}

      <div style={{ display: "grid", gap: 9 }}>
        {AGENT_ORDER.filter(k => perAgent[k]).map(k => {
          const a = AGENTS[k];
          const s = perAgent[k]!;
          return (
            <div key={k} style={{
              display: "grid", gridTemplateColumns: "28px 1fr", gap: 10,
              paddingBottom: 9, borderBottom: "1px dotted var(--line)",
            }}>
              <span aria-hidden style={{
                width: 26, height: 26, borderRadius: 3, background: a.color, color: "#fff",
                display: "grid", placeItems: "center",
                fontFamily: "var(--font-display)", fontSize: 13,
              }}>{a.mark}</span>
              <div>
                <div style={{ fontFamily: a.font, fontSize: 14, fontWeight: 600, color: a.color }}>
                  {a.name}
                </div>
                <p style={{
                  margin: "1px 0 0", fontSize: 13, lineHeight: 1.45,
                  fontFamily: k === "customer_service" ? "var(--font-type)" : "var(--font-body)",
                }}>{s}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* guardrails that fired */}
      {guards.length > 0 && (
        <div style={{
          marginTop: 14, padding: "11px 13px", borderRadius: 4,
          background: "rgba(200,145,47,.09)", border: "1px solid var(--gold)",
        }}>
          <div className="label" style={{ color: "var(--gold)", marginBottom: 6 }}>
            Guardrails that fired — the system holding, not failing
          </div>
          {guards.map((g, i) => (
            <div key={i} style={{ fontSize: 12.5, display: "flex", gap: 7, padding: "2px 0" }}>
              <span style={{ color: agentOf(g.agent).color, fontWeight: 600 }}>{agentOf(g.agent).name}</span>
              <span style={{ color: "var(--ink-soft)" }}>
                {g.result ?? g.error ?? g.stop_reason ?? g.purpose.replace(/_/g, " ")}
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{
        display: "flex", gap: 18, marginTop: 14, flexWrap: "wrap",
        fontFamily: "var(--font-condensed)", fontSize: 11.5,
        letterSpacing: ".1em", textTransform: "uppercase", color: "var(--ink-soft)",
      }}>
        <span>{seconds}s</span>
        <span>{tools} lookups</span>
        {cached > 0 && <span style={{ color: "var(--gold)" }}>{cached} reused</span>}
        <span>{events.length} wire entries</span>
      </div>
    </section>
  );
}

/** One sentence per agent, drawn from what it actually did. */
function summarise(events: AgentEvent[]): Record<string, string> {
  const out: Record<string, string> = {};
  const tools: Record<string, Set<string>> = {};
  const asked: Record<string, string[]> = {};
  const last: Record<string, string> = {};

  for (const e of events) {
    if (!AGENT_ORDER.includes(e.agent as any)) continue;
    tools[e.agent] ??= new Set();
    asked[e.agent] ??= [];
    if (e.purpose === "tool_call" && e.tool && !["ask_teammate", "final_result"].includes(e.tool)) {
      tools[e.agent].add(e.tool.replace(/_/g, " "));
    }
    if (e.purpose === "delegation_started") {
      asked[e.agent].push(String(e.tool_args?.teammate ?? "").replace(/_/g, " "));
    }
    if ((e.purpose === "delegation_done" || e.purpose === "agent_end" ||
         e.purpose === "run_finished") && e.result) {
      last[e.agent] = e.result;
    }
  }

  for (const k of AGENT_ORDER) {
    const t = [...(tools[k] ?? [])];
    const a = [...new Set(asked[k] ?? [])];
    if (!t.length && !a.length && !last[k]) continue;
    const parts: string[] = [];
    if (t.length) parts.push(`checked ${t.slice(0, 4).join(", ")}${t.length > 4 ? ` and ${t.length - 4} more` : ""}`);
    if (a.length) parts.push(`asked ${a.join(" and ")}`);
    const did = parts.length ? parts.join("; ") : "took part";
    out[k] = last[k] ? `${cap(did)}. ${last[k]}` : `${cap(did)}.`;
  }
  return out;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
