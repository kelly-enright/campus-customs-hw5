import Dan from "./Dan";

/**
 * The masthead, dressed as the plate on an office door: shop name, department,
 * and the three facts a person at this desk needs standing up — what day the
 * shop thinks it is, which model is doing the work, and whether the back end
 * is actually reachable.
 */
export default function Masthead({
  shopToday, model, online, busy,
}: { shopToday: string | null; model: string | null; online: boolean; busy: boolean }) {
  return (
    <header style={{ padding: "18px 0 14px" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 20, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ marginTop: 4 }}><Dan awake={busy} size={78} /></div>
          <div>
            <div className="label" style={{ color: "var(--gold)", marginBottom: 2 }}>
              Established New Haven
            </div>
            <h1 style={{
              fontSize: "clamp(26px,4vw,40px)", color: "var(--cream)", lineHeight: 1.05,
              textShadow: "2.5px 2.5px 0 var(--crimson)",
            }}>
              CAMPUS CUSTOMS
            </h1>
            <div className="label" style={{ color: "var(--paper-edge)", marginTop: 4, letterSpacing: ".3em" }}>
              Operations Desk &nbsp;·&nbsp; Back Office
            </div>
          </div>
        </div>

        <dl style={{
          display: "flex", gap: 26, margin: 0, flexWrap: "wrap",
          fontFamily: "var(--font-condensed)",
        }}>
          <Fact label="Shop date" value={shopToday ?? "—"} />
          <Fact label="Model" value={model ?? "—"} />
          <div>
            <dt className="label" style={{ color: "var(--paper-edge)" }}>Backend</dt>
            <dd style={{ margin: 0, display: "flex", alignItems: "center", gap: 7 }}>
              <span className={online ? "live-dot" : ""} style={{
                width: 9, height: 9, borderRadius: "50%",
                background: online ? "var(--ledger-light)" : "var(--crimson-light)",
                boxShadow: online ? "0 0 8px var(--ledger-light)" : "none",
              }} />
              <span style={{ color: "var(--cream)", fontSize: 15, fontWeight: 500 }}>
                {online ? "connected" : "offline"}
              </span>
            </dd>
          </div>
        </dl>
      </div>
      <div style={{
        height: 4, marginTop: 14,
        background: "repeating-linear-gradient(90deg,var(--gold) 0 26px,transparent 26px 32px)",
        opacity: .75,
      }} />
    </header>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label" style={{ color: "var(--paper-edge)" }}>{label}</dt>
      <dd style={{ margin: 0, color: "var(--cream)", fontSize: 15, fontWeight: 500 }}>{value}</dd>
    </div>
  );
}
