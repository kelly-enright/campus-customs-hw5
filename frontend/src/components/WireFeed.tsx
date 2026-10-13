import { useEffect, useRef } from "react";
import { agentOf, purposeLabel } from "../lib/agents";
import type { AgentEvent } from "../lib/api";

/**
 * The wire. Every agent action as it comes in, newest at the bottom, written in
 * that agent's own hand on that agent's own paper.
 *
 * It is a teletype, not a log viewer: fixed-width timestamps down the left,
 * a tear-off perforation at the top, and each line arriving with a slide rather
 * than appearing. Rule citations are set as small brass-coloured chips because
 * on this desk "why" matters as much as "what" — a refusal that cites CC-OPS-27
 * is the system working, and the feed should make that legible rather than
 * burying it.
 */
export default function WireFeed({
  events, running, height = 430,
}: { events: AgentEvent[]; running: boolean; height?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  // Follow the tail only while the reader is already at the bottom — yanking
  // them back down while they are reading an earlier line is hostile.
  useEffect(() => {
    const el = box.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  const onScroll = () => {
    const el = box.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  };

  return (
    <section aria-label="Agent wire" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: 17, color: "var(--cream)" }}>THE&nbsp;WIRE</h2>
        <span className="label" style={{ color: running ? "var(--gold)" : "var(--paper-edge)" }}>
          {running && <span className="live-dot" style={{ marginRight: 6 }}>●</span>}
          {events.length} entries
        </span>
      </div>
      <div style={{ height: 3, background: "var(--gold)", opacity: .6, margin: "8px 0 0" }} />

      {/* perforated tear strip */}
      <div aria-hidden style={{
        height: 13, background: "var(--paper)",
        borderLeft: "1px solid var(--paper-edge)", borderRight: "1px solid var(--paper-edge)",
        backgroundImage: "radial-gradient(circle at 7px 7px, var(--blotter) 2.4px, transparent 2.6px)",
        backgroundSize: "15px 15px", opacity: .9,
      }} />

      <div ref={box} onScroll={onScroll} style={{
        height, overflowY: "auto", background: "var(--paper)",
        border: "1px solid var(--paper-edge)", borderTop: "none",
        borderRadius: "0 0 var(--radius) var(--radius)",
        padding: "6px 0 14px", boxShadow: "var(--shadow-card)",
      }}>
        {events.length === 0 ? (
          <p style={{
            padding: "48px 24px", textAlign: "center", color: "var(--ink-soft)",
            fontStyle: "italic", margin: 0,
          }}>
            Nothing on the wire. Pick a ticket and send the team in.
          </p>
        ) : (
          events.map(e => <Line key={`${e.run_id}-${e.index}`} e={e} />)
        )}
        {running && (
          <div style={{
            padding: "9px 16px", display: "flex", alignItems: "center", gap: 9,
            color: "var(--ink-soft)", fontFamily: "var(--font-type)", fontSize: 13,
          }}>
            <span className="live-dot">▌</span> the team is still working…
          </div>
        )}
      </div>
    </section>
  );
}

function Line({ e }: { e: AgentEvent }) {
  const a = agentOf(e.agent);
  const bad = e.purpose.includes("refused") || e.purpose.includes("timeout")
           || e.purpose.includes("error") || !!e.error;
  const cached = e.purpose === "tool_cache_hit";
  const body = e.said ?? e.result ?? e.decision ?? "";

  return (
    <div className="slide-in" style={{
      display: "grid", gridTemplateColumns: "58px 1fr", gap: 10,
      padding: "5px 16px 5px 12px",
      borderLeft: `3px solid ${bad ? "var(--crimson)" : a.color}`,
      background: cached ? "rgba(200,145,47,.07)" : "transparent",
      marginLeft: e.depth ? e.depth * 14 : 0,
      opacity: cached ? .8 : 1,
    }}>
      <time className="num" style={{
        fontSize: 10.5, color: "var(--ink-soft)", paddingTop: 3, whiteSpace: "nowrap",
      }}>
        {e.elapsed_ms != null ? `+${(e.elapsed_ms / 1000).toFixed(1)}s` : ""}
      </time>

      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 7, flexWrap: "wrap" }}>
          <span style={{
            fontFamily: a.font, fontSize: 13.5, fontWeight: 600, color: a.color,
          }}>{a.name}</span>
          <span className="label" style={{ fontSize: 10, color: bad ? "var(--crimson)" : "var(--ink-soft)" }}>
            {purposeLabel(e.purpose)}
          </span>
          {e.tool && e.tool !== "final_result" && (
            <code style={{
              fontFamily: "var(--font-mono)", fontSize: 10.5,
              background: "var(--navy)", color: "var(--cream)",
              padding: "1px 6px", borderRadius: 3,
            }}>{e.tool}</code>
          )}
          {cached && <span className="label" style={{ fontSize: 9.5, color: "var(--gold)" }}>cached</span>}
        </div>

        {body && (
          <p style={{
            margin: "2px 0 0", fontSize: 13, lineHeight: 1.45,
            color: bad ? "var(--crimson)" : "var(--ink)",
            fontFamily: a.key === "customer_service" ? "var(--font-type)" : "var(--font-body)",
            fontStyle: bad ? "italic" : "normal",
          }}>{body}</p>
        )}

        {e.error && (
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--crimson)", fontStyle: "italic" }}>
            {e.error}
          </p>
        )}

        {e.rules?.length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
            {e.rules.map(r => (
              <span key={r} style={{
                fontFamily: "var(--font-condensed)", fontSize: 9.5, letterSpacing: ".07em",
                border: "1px solid var(--gold)", color: "var(--gold)",
                padding: "0 5px", borderRadius: 2, background: "rgba(200,145,47,.1)",
              }}>{r}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
