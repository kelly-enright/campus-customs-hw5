import type { Ticket } from "../lib/api";

/**
 * The wire tray. Tickets are docket cards stacked in an in-tray — selecting one
 * pulls it forward, and a resolved ticket gets the RESOLVED stamp pressed onto
 * it rather than being greyed out or removed.
 *
 * Why cards and not a table: a ticket is a physical thing on this desk. A table
 * row says "database"; a card with a punch hole and a stamp says "the thing you
 * are about to work on".
 */

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Discount request",
};

export default function TicketTray({
  tickets, selected, onSelect, runningId,
}: {
  tickets: Ticket[];
  selected: number | null;
  onSelect: (id: number) => void;
  runningId: number | null;
}) {
  return (
    <section aria-label="Ticket tray">
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 style={{ fontSize: 17, color: "var(--cream)" }}>IN&nbsp;TRAY</h2>
        <span className="label" style={{ color: "var(--paper-edge)" }}>
          {tickets.filter(t => t.is_open).length} open / {tickets.length}
        </span>
      </div>
      <div style={{ height: 3, background: "var(--gold)", opacity: .6, margin: "8px 0 14px" }} />

      <div style={{ display: "grid", gap: 12 }}>
        {tickets.map((t, i) => {
          const active = selected === t.id;
          const running = runningId === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onSelect(t.id)}
              className="sheet drop-in"
              aria-pressed={active}
              style={{
                animationDelay: `${i * 70}ms`,
                textAlign: "left", cursor: "pointer", padding: "13px 15px 14px",
                borderLeft: `6px solid ${active ? "var(--crimson)" : "var(--paper-edge)"}`,
                transform: active ? "translateX(7px)" : "none",
                transition: "transform .18s cubic-bezier(.2,.9,.3,1), border-color .18s, box-shadow .18s",
                boxShadow: active
                  ? "0 2px 3px rgba(22,40,61,.14), 0 14px 30px rgba(22,40,61,.28)"
                  : "var(--shadow-card)",
                font: "inherit", color: "inherit", position: "relative",
              }}
            >
              {/* punch hole, so it reads as a filed docket card */}
              <span aria-hidden style={{
                position: "absolute", top: 13, right: 13, width: 11, height: 11,
                borderRadius: "50%", background: "var(--blotter)", opacity: .17,
                boxShadow: "inset 0 1px 2px rgba(0,0,0,.4)",
              }} />

              <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 5 }}>
                <span className="num" style={{
                  fontSize: 25, fontWeight: 700, color: "var(--crimson)", lineHeight: 1,
                }}>{t.id}</span>
                <span className="label">{TYPE_LABEL[t.type] ?? t.type}</span>
              </div>

              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 2 }}>{t.subject}</div>
              <div style={{ fontSize: 13.5, color: "var(--ink-soft)", fontStyle: "italic" }}>
                {t.requester}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 9, marginTop: 11, flexWrap: "wrap" }}>
                {running ? (
                  <span className="stamp pending stamp-in" style={{ color: "var(--crimson)" }}>
                    ● Working
                  </span>
                ) : t.is_open ? (
                  <span className="stamp open">Open</span>
                ) : (
                  <span className="stamp resolved stamp-in">Resolved</span>
                )}
                {t.pending_approvals > 0 && (
                  <span className="label" style={{ color: "var(--gold)" }}>
                    {t.pending_approvals} awaiting you
                  </span>
                )}
                {t.sku && (
                  <span className="num" style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                    {t.sku}{t.size ? ` · ${t.size}` : ""}{t.qty ? ` · ×${t.qty}` : ""}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
