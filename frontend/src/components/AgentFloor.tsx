import { AGENTS, AGENT_ORDER, type AgentKey } from "../lib/agents";
import type { AgentEvent } from "../lib/api";

/**
 * The floor: five desks, one per agent.
 *
 * Each desk shows the agent's own stationery — its colour, its typeface, its
 * paper — so the five read as different people rather than five rows of the
 * same component. A desk lights up while its agent is working, shows what it is
 * doing right now, and keeps a count of the tools it has used.
 *
 * Delegation is drawn as a line of ink between desks: when Accounting asks
 * Facilities, a labelled thread appears underneath. That edge is the whole
 * point of a fully connected team, and a list of events alone never shows it.
 */

type Props = { events: AgentEvent[]; running: boolean };

export default function AgentFloor({ events, running }: Props) {
  const state = buildState(events);
  const edges = buildEdges(events);

  return (
    <section aria-label="Agent floor">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: 17, color: "var(--cream)" }}>THE&nbsp;FLOOR</h2>
        <span className="label" style={{ color: "var(--paper-edge)" }}>
          {running ? "team at work" : "all quiet"}
        </span>
      </div>
      <div style={{ height: 3, background: "var(--gold)", opacity: .6, margin: "8px 0 14px" }} />

      <div style={{
        display: "grid", gap: 10,
        gridTemplateColumns: "repeat(auto-fit,minmax(176px,1fr))",
      }}>
        {AGENT_ORDER.map(key => {
          const a = AGENTS[key];
          const s = state[key];
          const busy = s.status === "working";
          return (
            <article key={key} className="sheet" style={{
              padding: "12px 13px 13px", background: a.paper,
              borderTop: `4px solid ${a.color}`,
              opacity: s.status === "idle" ? .62 : 1,
              transform: busy ? "translateY(-3px)" : "none",
              boxShadow: busy
                ? `0 2px 3px rgba(22,40,61,.12), 0 14px 28px rgba(22,40,61,.26), 0 0 0 2px ${a.color}`
                : "var(--shadow-card)",
              transition: "transform .22s cubic-bezier(.2,.9,.3,1), box-shadow .22s, opacity .22s",
              position: "relative", overflow: "hidden",
            }}>
              {/* nameplate */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                <span aria-hidden style={{
                  width: 27, height: 27, borderRadius: 3, flexShrink: 0,
                  background: a.color, color: a.paper,
                  display: "grid", placeItems: "center",
                  fontFamily: "var(--font-display)", fontSize: 14,
                  boxShadow: "1.5px 1.5px 0 rgba(22,40,61,.4)",
                }}>{a.mark}</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontFamily: a.font, fontSize: a.key === "boss" ? 14 : 15,
                    color: a.color, lineHeight: 1.15, fontWeight: 600,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>{a.name}</div>
                  <div className="label" style={{ fontSize: 9.5, letterSpacing: ".18em" }}>{a.role}</div>
                </div>
                {busy && (
                  <span className="writing" aria-label="working" style={{
                    marginLeft: "auto", fontSize: 15, color: a.color,
                  }}>✒</span>
                )}
              </div>

              {/* what they are doing, or what they did */}
              <div style={{
                fontSize: 12.5, lineHeight: 1.4, minHeight: 34,
                color: s.status === "idle" ? "var(--ink-soft)" : "var(--ink)",
                fontStyle: s.status === "idle" ? "italic" : "normal",
              }}>
                {s.status === "idle" ? "at their desk" : s.note}
              </div>

              <div style={{
                marginTop: 9, paddingTop: 7, borderTop: `1px dotted ${a.color}`,
                display: "flex", justifyContent: "space-between",
                fontFamily: "var(--font-condensed)", fontSize: 10.5,
                letterSpacing: ".1em", textTransform: "uppercase", color: "var(--ink-soft)",
              }}>
                <span>{s.tools} lookup{s.tools === 1 ? "" : "s"}</span>
                <span style={{ color: s.status === "done" ? "var(--ledger)" : a.color }}>
                  {s.status === "done" ? "reported" : s.status === "working" ? "working" : "idle"}
                </span>
              </div>

              {busy && (
                <span aria-hidden style={{
                  position: "absolute", left: 0, right: 0, bottom: 0, height: 3,
                  background: `linear-gradient(90deg, transparent, ${a.color}, transparent)`,
                  animation: "slide-in 1.1s ease-in-out infinite alternate",
                }} />
              )}
            </article>
          );
        })}
      </div>

      {/* the mesh, made visible */}
      {edges.length > 0 && (
        <div className="sheet" style={{ marginTop: 11, padding: "11px 14px 12px" }}>
          <div className="label" style={{ marginBottom: 8 }}>
            Who asked whom &nbsp;·&nbsp; {edges.length} hand-off{edges.length === 1 ? "" : "s"}
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {edges.map((e, i) => {
              const from = AGENTS[e.from as AgentKey] ?? AGENTS.boss;
              const to = AGENTS[e.to as AgentKey] ?? AGENTS.boss;
              const bad = e.status === "refused" || e.status === "timeout";
              return (
                <div key={i} className="slide-in" style={{
                  animationDelay: `${i * 50}ms`,
                  display: "flex", alignItems: "center", gap: 8, fontSize: 12.5,
                  paddingLeft: e.depth * 15,
                }}>
                  <Pip a={from} /> 
                  <span aria-hidden style={{
                    flex: "0 0 30px", height: 2, borderRadius: 2,
                    background: bad
                      ? "repeating-linear-gradient(90deg,var(--crimson) 0 4px,transparent 4px 7px)"
                      : `linear-gradient(90deg,${from.color},${to.color})`,
                  }} />
                  <Pip a={to} />
                  <span style={{
                    color: bad ? "var(--crimson)" : "var(--ink-soft)",
                    fontStyle: bad ? "italic" : "normal",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {bad ? (e.status === "refused" ? "refused — against the rules" : "no answer in time")
                         : e.question}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

function Pip({ a }: { a: { color: string; mark: string; name: string } }) {
  return (
    <span title={a.name} style={{
      width: 19, height: 19, flexShrink: 0, borderRadius: 3, background: a.color,
      color: "#fff", display: "grid", placeItems: "center",
      fontFamily: "var(--font-condensed)", fontSize: 10.5, fontWeight: 700,
    }}>{a.mark}</span>
  );
}

/* ---------- deriving desk state from the event stream ---------- */

type DeskState = { status: "idle" | "working" | "done"; note: string; tools: number };

function buildState(events: AgentEvent[]): Record<string, DeskState> {
  const base: Record<string, DeskState> = {};
  for (const k of AGENT_ORDER) base[k] = { status: "idle", note: "", tools: 0 };

  for (const e of events) {
    const d = base[e.agent];
    if (!d) continue;
    if (e.purpose === "tool_call" && e.tool && e.tool !== "ask_teammate" && e.tool !== "final_result") {
      d.tools += 1;
      d.status = "working";
      d.note = `looking up ${e.tool.replace(/_/g, " ")}`;
    } else if (e.purpose === "tool_cache_hit") {
      d.status = "working";
      d.note = `reused ${(e.tool ?? "").replace(/_/g, " ")}`;
    } else if (e.purpose === "model_request") {
      d.status = "working";
      if (!d.note) d.note = "thinking it over";
    } else if (e.purpose === "delegation_started") {
      d.status = "working";
      d.note = `asked ${(e.tool_args?.teammate as string ?? "a colleague").replace(/_/g, " ")}`;
    } else if (e.purpose === "delegation_refused") {
      d.note = "hand-off refused by the rules";
    } else if (e.purpose === "agent_end" || e.purpose === "delegation_done") {
      d.status = "done";
      d.note = e.result ? truncate(e.result, 110) : "reported back";
    } else if (e.purpose === "run_finished" || e.purpose === "run_error") {
      if (base.boss) { base.boss.status = "done"; base.boss.note = truncate(e.result ?? "closed the run", 110); }
    }
  }
  return base;
}

type Edge = { from: string; to: string; question: string; depth: number; status: string };

function buildEdges(events: AgentEvent[]): Edge[] {
  const edges: Edge[] = [];
  for (const e of events) {
    if (e.purpose === "delegation_started") {
      edges.push({
        from: e.agent,
        to: String(e.tool_args?.teammate ?? "?"),
        question: truncate(String(e.tool_args?.question ?? ""), 78),
        depth: e.depth ?? 0,
        status: "asked",
      });
    } else if (e.purpose === "delegation_refused") {
      edges.push({
        from: e.agent, to: String(e.tool_args?.teammate ?? "?"),
        question: "", depth: e.depth ?? 0, status: "refused",
      });
    } else if (e.purpose === "delegation_timeout") {
      const last = [...edges].reverse().find(x => x.to === e.agent && x.status === "asked");
      if (last) last.status = "timeout";
    }
  }
  return edges;
}

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
