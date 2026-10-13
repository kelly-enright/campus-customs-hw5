import { useCallback, useEffect, useRef, useState } from "react";
import Masthead from "./components/Masthead";
import TicketTray from "./components/TicketTray";
import AgentFloor from "./components/AgentFloor";
import WireFeed from "./components/WireFeed";
import ApprovalTray from "./components/ApprovalTray";
import CashDrawer from "./components/CashDrawer";
import RunSummary from "./components/RunSummary";
import {
  ApiError, decideApproval, getApprovals, getCash, getEvents, getHealth,
  getTicketEvents, getTickets, resetDb, runTicket,
  type AgentEvent, type Approval, type Cash, type Ticket,
} from "./lib/api";

/**
 * The Campus Customs operations desk.
 *
 * Layout is a three-column desk rather than a dashboard grid: the in-tray on
 * the left where work arrives, the floor and the wire in the middle where it
 * gets done, and your own desk on the right where things need a signature.
 * Work moves left to right, which is how a desk actually reads.
 */
export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [shopToday, setShopToday] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [approver, setApprover] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [refusal, setRefusal] = useState<{ id: number; message: string; detail?: any } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [online, setOnline] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [historic, setHistoric] = useState(false);
  const since = useRef(0);

  const refreshBoard = useCallback(async () => {
    try {
      const [t, a, c] = await Promise.all([getTickets(), getApprovals(), getCash()]);
      setTickets(t.tickets);
      setShopToday(t.shop_today);
      setApprovals(a.approvals);
      setCash(c);
      setOnline(true);
      setError(null);
      setSelected(s => s ?? t.tickets[0]?.id ?? null);
    } catch (e) {
      setOnline(false);
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    getHealth().then(h => { setModel(h.model); setOnline(true); }).catch(() => setOnline(false));
    refreshBoard();
  }, [refreshBoard]);

  // Follow a live run. Polls only what is new via `since`, so a long run does
  // not re-send its whole trail on every tick.
  useEffect(() => {
    if (!runId || !running) return;
    let alive = true;
    const tick = async () => {
      try {
        const r = await getEvents(runId, since.current);
        if (!alive) return;
        if (r.events.length) {
          since.current = r.next_since;
          setEvents(prev => [...prev, ...r.events]);
        }
        if (r.run_finished) {
          setRunning(false);
          refreshBoard();       // the ticket may now be resolved, cash may have moved
        }
      } catch { /* a dropped poll is not worth surfacing; the next one retries */ }
    };
    const id = setInterval(tick, 1800);
    tick();
    return () => { alive = false; clearInterval(id); };
  }, [runId, running, refreshBoard]);

  // Selecting a ticket while nothing is running pulls up its most recent run,
  // so a resolved ticket can be reviewed rather than appearing as a blank wire.
  // A finished ticket still has a story, and the desk should be able to tell it.
  useEffect(() => {
    if (selected == null || running) return;
    let alive = true;
    getTicketEvents(selected)
      .then(r => {
        if (!alive) return;
        const lastRun = r.events.length ? r.events[r.events.length - 1].run_id : null;
        const latest = lastRun ? r.events.filter(e => e.run_id === lastRun) : [];
        setEvents(latest);
        setHistoric(latest.length > 0);
      })
      .catch(() => { /* no history is fine — the wire just stays empty */ });
    return () => { alive = false; };
  }, [selected, running]);

  const start = async () => {
    if (selected == null) return;
    setError(null); setRefusal(null); setEvents([]); since.current = 0;
    try {
      const r = await runTicket(selected);
      setRunId(r.run_id);
      setRunning(true);
      setHistoric(false);
      setModel(r.model);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  const decide = async (id: number, decision: "approve" | "reject") => {
    setBusyId(id); setRefusal(null);
    try {
      await decideApproval(id, approver.trim(), decision);
      await refreshBoard();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // The shop's rules declined. That is information, not a failure.
        setRefusal({ id, message: e.message, detail: e.detail });
      } else {
        setError(e instanceof ApiError ? e.message : String(e));
      }
    } finally {
      setBusyId(null);
    }
  };

  const doReset = async () => {
    setResetting(true); setError(null); setRefusal(null);
    try {
      await resetDb();
      setEvents([]); setRunId(null); since.current = 0; setHistoric(false);
      await refreshBoard();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setResetting(false);
    }
  };

  const ticket = tickets.find(t => t.id === selected) ?? null;
  const runningTicket = running ? (events[0]?.ticket_id ?? selected) : null;

  return (
    <div style={{ maxWidth: 1480, margin: "0 auto", padding: "0 22px 64px" }}>
      <Masthead shopToday={shopToday} model={model} online={online} busy={running} />

      {error && (
        <div className="sheet" role="alert" style={{
          padding: "12px 16px", marginBottom: 16,
          borderLeft: "6px solid var(--crimson)", background: "#fdf0ec",
        }}>
          <span className="label" style={{ color: "var(--crimson)" }}>Desk closed</span>
          <p style={{ margin: "3px 0 0", fontSize: 14 }}>{error}</p>
        </div>
      )}

      {/* command strip */}
      <div className="sheet" style={{
        display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
        padding: "12px 16px", marginBottom: 18,
      }}>
        <div style={{ flex: "1 1 240px", minWidth: 0 }}>
          <span className="label">Selected</span>
          <div style={{ fontSize: 15.5, fontWeight: 600, marginTop: 1 }}>
            {ticket ? `#${ticket.id} — ${ticket.subject}` : "no ticket selected"}
          </div>
        </div>
        <button className="btn primary" onClick={start}
                disabled={!ticket || running || !online || !ticket.is_open}
                title={ticket && !ticket.is_open ? "This ticket is already resolved" : ""}>
          {running ? "Team at work…" : "Send the team in"}
        </button>
        <button className="btn" onClick={doReset} disabled={running || resetting || !online}>
          {resetting ? "Resetting…" : "Reset the day"}
        </button>
      </div>

      {/* the desk itself */}
      <div style={{
        display: "grid", gap: 18,
        gridTemplateColumns: "minmax(252px,.82fr) minmax(400px,1.7fr) minmax(290px,1fr)",
        alignItems: "start",
      }} className="desk-grid">
        <div style={{ display: "grid", gap: 18 }}>
          <TicketTray tickets={tickets} selected={selected} onSelect={setSelected}
                      runningId={runningTicket} />
        </div>

        <div style={{ display: "grid", gap: 18, minWidth: 0 }}>
          <AgentFloor events={events} running={running} />
          {historic && !running && (
            <div className="label" style={{ color: "var(--gold)", marginTop: -8 }}>
              showing the last run for ticket {selected} — from the audit trail
            </div>
          )}
          <WireFeed events={events} running={running} />
          <RunSummary events={events} />
        </div>

        <div style={{ display: "grid", gap: 18 }}>
          <CashDrawer cash={cash} />
          <ApprovalTray
            approvals={approvals} approver={approver} onApprover={setApprover}
            onDecide={decide} busyId={busyId} refusal={refusal}
          />
        </div>
      </div>

      <footer style={{
        marginTop: 34, paddingTop: 14, borderTop: "1px solid rgba(255,250,240,.2)",
        display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap",
        fontFamily: "var(--font-condensed)", fontSize: 11.5, letterSpacing: ".12em",
        textTransform: "uppercase", color: "var(--paper-edge)",
      }}>
        <span>Campus Customs · Operations Desk</span>
        <span>Agents prepare · only a person approves</span>
      </footer>
    </div>
  );
}
