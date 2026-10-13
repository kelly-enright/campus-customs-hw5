import { useEffect, useRef, useState } from "react";
import type { Cash } from "../lib/api";

/**
 * The cash drawer, under the counter on green felt.
 *
 * The balance counts down digit by digit when it drops, because the brief asks
 * that an approved payment be visibly felt. A number that simply swaps from
 * 3,400 to 1,000 is easy to miss; one that rolls down makes a person look. The
 * drawer also flashes crimson on the way down and never on the way up — in this
 * shop money only leaves (CC-OPS-36).
 */
export default function CashDrawer({ cash }: { cash: Cash | null }) {
  const balance = cash?.checking_balance ?? null;
  const [shown, setShown] = useState<number | null>(balance);
  const [dropping, setDropping] = useState(false);
  const prev = useRef<number | null>(balance);

  useEffect(() => {
    if (balance === null) return;
    const from = prev.current;
    prev.current = balance;
    if (from === null || from === balance) { setShown(balance); return; }

    setDropping(from > balance);
    const start = performance.now();
    const dur = 900;
    let raf = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(from + (balance - from) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
      else setTimeout(() => setDropping(false), 420);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [balance]);

  const floor = cash?.cash_floor ?? 0;
  const pctToFloor = balance !== null && balance > 0
    ? Math.max(0, Math.min(100, (floor / balance) * 100)) : 0;

  return (
    <section aria-label="Cash drawer" className="sheet" style={{
      padding: 0, overflow: "hidden",
      background: "linear-gradient(170deg, var(--felt) 0%, #263e34 100%)",
      borderColor: "#1b2e26",
    }}>
      <div style={{
        padding: "11px 16px 9px",
        borderBottom: "1px solid rgba(255,255,255,.14)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span className="label" style={{ color: "#bfe3d2", letterSpacing: ".22em" }}>Cash Drawer</span>
        <span className="label" style={{ color: "#8fb9a6" }}>checking</span>
      </div>

      <div style={{ padding: "16px 16px 14px", textAlign: "center" }}>
        <div className="num" style={{
          fontSize: 42, fontWeight: 700, lineHeight: 1,
          color: dropping ? "var(--crimson-light)" : "#e9f7ef",
          textShadow: dropping ? "0 0 20px rgba(184,67,46,.55)" : "0 2px 0 rgba(0,0,0,.3)",
          transition: "color .3s, text-shadow .3s",
          fontVariantNumeric: "tabular-nums",
        }}>
          {shown === null ? "—" : `$${shown.toLocaleString("en-US", {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
          })}`}
        </div>
        {cash?.outflow_only && (
          <div className="label" style={{ color: "#7fa894", marginTop: 7, letterSpacing: ".12em" }}>
            ↓ outflow only — no revenue modelled
          </div>
        )}
      </div>

      {/* reserve floor, drawn as a line the balance must not fall past */}
      <div style={{ padding: "0 16px 14px" }}>
        <div style={{ position: "relative", height: 9, borderRadius: 5, background: "rgba(0,0,0,.3)", overflow: "hidden" }}>
          <div style={{
            position: "absolute", inset: 0,
            background: "linear-gradient(90deg, var(--ledger-light), #9fe3c6)",
            transformOrigin: "left", transform: `scaleX(${1 - pctToFloor / 100})`,
            transition: "transform .9s cubic-bezier(.2,.9,.3,1)",
          }} />
          <div style={{
            position: "absolute", left: `${pctToFloor}%`, top: -3, bottom: -3, width: 3,
            background: "var(--gold)", boxShadow: "0 0 7px var(--gold)",
          }} title={`Reserve floor $${floor}`} />
        </div>
        <div style={{
          display: "flex", justifyContent: "space-between", marginTop: 6,
          fontFamily: "var(--font-condensed)", fontSize: 11, color: "#8fb9a6",
          letterSpacing: ".08em", textTransform: "uppercase",
        }}>
          <span>floor ${floor.toLocaleString()}</span>
          <span>spendable ${(cash?.spendable_above_floor ?? 0).toLocaleString()}</span>
        </div>
      </div>

      {/* what is claiming this money */}
      {cash?.obligations?.length ? (
        <div style={{ borderTop: "1px solid rgba(255,255,255,.14)", padding: "11px 16px 14px" }}>
          <div className="label" style={{ color: "#bfe3d2", marginBottom: 7 }}>Claims against it</div>
          {cash.obligations.map(o => {
            const blocked = cash.blocked_by_floor?.some(b => b.label === o.label);
            return (
              <div key={o.label} style={{
                display: "flex", justifyContent: "space-between", gap: 10,
                padding: "5px 0", borderBottom: "1px dotted rgba(255,255,255,.14)",
                fontSize: 13, color: blocked ? "#f0b4a6" : "#dff0e6",
              }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span className="num" style={{
                    fontSize: 10, border: "1px solid currentColor", borderRadius: 3,
                    padding: "0 4px", opacity: .75,
                  }}>P{o.priority}</span>
                  {o.label}
                  {o.is_overdue && <span style={{ color: "var(--gold-light)", fontSize: 11 }}>overdue</span>}
                </span>
                <span className="num" style={{ whiteSpace: "nowrap", fontWeight: 600 }}>
                  ${o.amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
              </div>
            );
          })}
          {cash.escalation_required && (
            <div style={{
              marginTop: 10, padding: "8px 11px", borderRadius: 4,
              background: "rgba(158,43,28,.3)", border: "1px solid rgba(240,180,166,.4)",
              color: "#ffd9cf", fontSize: 12.5, lineHeight: 1.45,
            }}>
              Not everything here can be paid without breaking the floor. The red line
              is a decision for you, not for the agents.
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
