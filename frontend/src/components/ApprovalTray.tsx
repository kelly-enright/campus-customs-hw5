import { useState } from "react";
import { agentOf } from "../lib/agents";
import type { Approval } from "../lib/api";

/**
 * The approval tray — the one place on this desk where a person, not an agent,
 * changes the world.
 *
 * Design intent: these cards are deliberately the heaviest objects on screen.
 * Payments are set on ledger-ruled paper with the amount in large tabular
 * figures; drafted letters appear as carbon copies in a typewriter face, folded
 * corner and all. The difference matters because approving a $2,400 payment and
 * approving a letter are not the same act, and a uniform row of buttons would
 * imply they were.
 *
 * A refusal from the server (409) is rendered in place as an explanation, not a
 * toast — when the shop's rules decline a payment, that is the system working
 * and the reason is the most useful thing on screen.
 */
export default function ApprovalTray({
  approvals, approver, onApprover, onDecide, busyId, refusal,
}: {
  approvals: Approval[];
  approver: string;
  onApprover: (v: string) => void;
  onDecide: (id: number, decision: "approve" | "reject") => void;
  busyId: number | null;
  refusal: { id: number; message: string; detail?: any } | null;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const money = approvals.filter(a => a.amount != null);
  const total = money.reduce((s, a) => s + (a.amount ?? 0), 0);

  return (
    <section aria-label="Approval tray">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: 17, color: "var(--cream)" }}>YOUR&nbsp;DESK</h2>
        <span className="label" style={{ color: approvals.length ? "var(--gold)" : "var(--paper-edge)" }}>
          {approvals.length} awaiting you
        </span>
      </div>
      <div style={{ height: 3, background: "var(--gold)", opacity: .6, margin: "8px 0 12px" }} />

      {approvals.length === 0 ? (
        <div className="sheet" style={{ padding: "26px 20px", textAlign: "center" }}>
          <p style={{ margin: 0, color: "var(--ink-soft)", fontStyle: "italic", fontSize: 14 }}>
            Nothing needs you right now.
          </p>
          <p style={{ margin: "5px 0 0", fontSize: 12.5, color: "var(--ink-soft)" }}>
            Agents prepare; only you approve.
          </p>
        </div>
      ) : (
        <>
          {/* who is signing — recorded against every payment */}
          <div className="sheet" style={{ padding: "10px 13px", marginBottom: 11 }}>
            <label className="label" htmlFor="approver" style={{ display: "block", marginBottom: 5 }}>
              Signing as
            </label>
            <input
              id="approver" value={approver} onChange={e => onApprover(e.target.value)}
              placeholder="your name"
              style={{
                width: "100%", padding: "7px 10px", font: "inherit", fontSize: 14.5,
                fontFamily: "var(--font-type)", background: "var(--cream)",
                border: "1px solid var(--paper-edge)", borderBottom: "2px solid var(--ink)",
                borderRadius: "3px 3px 0 0", color: "var(--ink)",
              }}
            />
            <p style={{ margin: "5px 0 0", fontSize: 11.5, color: "var(--ink-soft)" }}>
              Goes on the payment record. An agent's name is never accepted here.
            </p>
          </div>

          {money.length > 1 && (
            <div className="label" style={{ color: "var(--gold)", marginBottom: 9, textAlign: "right" }}>
              ${total.toLocaleString("en-US", { minimumFractionDigits: 2 })} queued in total
            </div>
          )}

          <div style={{ display: "grid", gap: 11 }}>
            {approvals.map((a, i) => (
              <Card
                key={a.id} a={a} index={i}
                expanded={open === a.id}
                onToggle={() => setOpen(open === a.id ? null : a.id)}
                canSign={approver.trim().length > 0}
                busy={busyId === a.id}
                refusal={refusal?.id === a.id ? refusal : null}
                onDecide={onDecide}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Card({
  a, index, expanded, onToggle, canSign, busy, refusal, onDecide,
}: {
  a: Approval; index: number; expanded: boolean; onToggle: () => void;
  canSign: boolean; busy: boolean;
  refusal: { message: string; detail?: any } | null;
  onDecide: (id: number, d: "approve" | "reject") => void;
}) {
  const by = agentOf(a.prepared_by);
  const isMoney = a.amount != null;
  const isLetter = a.kind === "customer_message";
  const rules = (a.rule_ids ?? "").split(",").filter(Boolean);

  return (
    <article className="sheet drop-in" style={{
      animationDelay: `${index * 80}ms`, padding: 0, overflow: "hidden",
      borderLeft: `6px solid ${isMoney ? "var(--ledger)" : by.color}`,
      // ledger ruling for money; plain carbon stock for letters
      backgroundImage: isMoney
        ? "repeating-linear-gradient(transparent 0 25px, rgba(29,107,79,.1) 25px 26px)"
        : undefined,
      background: isLetter ? "#fbf3ec" : undefined,
    }}>
      <div style={{ padding: "12px 14px 11px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
          <div style={{ minWidth: 0 }}>
            <span className="label" style={{ color: by.color }}>
              {a.kind === "payment" ? "Payment" : a.kind === "purchase_order" ? "Purchase order" : "Letter — draft"}
              {" · "}prepared by {by.name}
            </span>
            <div style={{
              fontSize: 14.5, marginTop: 3, lineHeight: 1.35,
              fontFamily: isLetter ? "var(--font-type)" : "var(--font-body)",
            }}>{a.summary}</div>
          </div>
          {isMoney && (
            <div className="num" style={{
              fontSize: 25, fontWeight: 700, color: "var(--ledger)",
              whiteSpace: "nowrap", lineHeight: 1.1,
            }}>
              ${a.amount!.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
          )}
        </div>

        {a.reason && (
          <p style={{ margin: "7px 0 0", fontSize: 12.5, color: "var(--ink-soft)", fontStyle: "italic" }}>
            {a.reason}
          </p>
        )}

        {rules.length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 7 }}>
            {rules.map(r => (
              <span key={r} style={{
                fontFamily: "var(--font-condensed)", fontSize: 9.5, letterSpacing: ".07em",
                border: "1px solid var(--gold)", color: "var(--gold)",
                padding: "0 5px", borderRadius: 2, background: "rgba(200,145,47,.1)",
              }}>{r.trim()}</span>
            ))}
          </div>
        )}

        {/* the letter itself, as a carbon copy */}
        {expanded && (
          <pre style={{
            margin: "10px 0 0", padding: "11px 13px", whiteSpace: "pre-wrap",
            fontFamily: isLetter ? "var(--font-type)" : "var(--font-mono)",
            fontSize: 12.5, lineHeight: 1.5,
            background: isLetter ? "#f6ece2" : "var(--cream)",
            border: "1px dashed var(--paper-edge)", borderRadius: 3,
            color: isLetter ? "var(--carbon)" : "var(--ink)",
            maxHeight: 260, overflow: "auto",
          }}>
            {isLetter
              ? `To: ${a.payload?.to ?? "—"}\nSubject: ${a.payload?.subject ?? "—"}\n\n${a.payload?.body ?? ""}`
              : JSON.stringify(a.payload, null, 2)}
          </pre>
        )}

        {refusal && (
          <div className="stamp-in" style={{
            marginTop: 10, padding: "10px 12px", borderRadius: 4,
            background: "rgba(158,43,28,.09)", border: "2px solid var(--stamp-red)",
          }}>
            <div className="label" style={{ color: "var(--stamp-red)", marginBottom: 3 }}>
              Refused by the shop's rules
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "var(--ink)" }}>{refusal.message}</p>
            {refusal.detail?.override && (
              <p style={{ margin: "5px 0 0", fontSize: 12, color: "var(--ink-soft)", fontStyle: "italic" }}>
                {refusal.detail.override}
              </p>
            )}
          </div>
        )}
      </div>

      <div style={{
        display: "flex", gap: 8, padding: "9px 14px 12px", flexWrap: "wrap",
        borderTop: "1px dashed var(--paper-edge)",
      }}>
        <button className="btn go small" disabled={!canSign || busy}
                onClick={() => onDecide(a.id, "approve")}
                title={canSign ? "" : "Enter your name first"}>
          {busy ? "…" : isMoney ? "Approve & pay" : "Approve"}
        </button>
        <button className="btn small" disabled={!canSign || busy}
                onClick={() => onDecide(a.id, "reject")}>Reject</button>
        <button className="btn small" onClick={onToggle} style={{ marginLeft: "auto" }}>
          {expanded ? "Hide" : isLetter ? "Read letter" : "Details"}
        </button>
      </div>
    </article>
  );
}
