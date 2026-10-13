# Campus Customs — Multi-Agent Operations

**HW 5.** Campus Customs is a New Haven merch shop. Tickets land on a board — customer
orders, rent, unpaid bills, discount requests — and a team of five agents works them
while a human approves anything that moves money.

Three pieces that talk to each other:

| Piece | What it is | Port |
|---|---|---|
| `mcp_server/` | FastMCP server — 14 tools, the only path to the shop database | stdio / 8001 |
| `backend/` | FastAPI + five PydanticAI agents, fully connected | 8000 |
| `frontend/` | React + Vite + TypeScript operations desk | 5173 |

One model throughout: **`gpt-6-luna` via Portkey.** The name appears once in code, at
`backend/agents/config.py`, read from `MODEL_NAME`.

---

## Running it

Five steps, in order. Steps 1–2 are once; steps 3–5 are every session.

### 1. Install

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Set the key

Copy `.env.example` to `.env` here (or in any parent folder) and fill in
`PORTKEY_API_KEY`. `backend/agents/config.py` walks up the directory tree and loads the
nearest one it finds. **The real `.env` is gitignored and is not in this repository.**

### 3. Make a clean working copy of the database

`data/campus_customs.db` is the original and is never written to. The agents and tools
read and write `data/campus_customs_new.db`. Both are committed here, so you can start
immediately — but any time you want a clean run, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Equivalently, `./.venv/bin/python backend/reset_db.py`, which does the same copy and
then prints the restored state so you can see it worked.

A clean board is: three open tickets, **$3,400.00** in checking, no payments, no
approval queue, invoice #501 open at $840.

### 4. Start the MCP server

The backend and the agents launch this themselves over stdio using `.mcp.json`, so for
normal use **you do not need to start it by hand.** To run it standalone — to inspect
the tools, or to point a vibe coder at it:

```bash
cd mcp_server
../.venv/bin/python server.py           # stdio
../.venv/bin/python server.py --http    # http://127.0.0.1:8001/mcp
```

Port 8001 deliberately, so 8000 stays free for the backend.

### 5. Start the FastAPI backend

From the `backend/` folder:

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

<http://localhost:8000> · API docs at <http://localhost:8000/docs>.
`GET /health` does a real MCP round trip, so a green response means the whole chain
works, not just that the web server is up.

### 6. Start the React board

From the `frontend/` folder:

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>. Pick a ticket, press **Send the team in**, watch the wire,
and approve what lands on your desk. The board talks to the backend at
`http://localhost:8000`, which allows the Vite origin via CORS.

**Stopping:** kill the whole process, not just the port.

```bash
pkill -f "uvicorn main:app"; pkill -f vite
```

---

## Resetting before a full three-ticket run

**Reset the database before any full run**, or the second run inherits the first run's
decisions and the cash math will not reconcile. Either:

```bash
./.venv/bin/python backend/run_ticket.py --all --reset
```

which resets and then works tickets 101, 102 and 103 in order — or reset separately and
drive it from the dashboard:

```bash
./.venv/bin/python backend/reset_db.py        # or POST /reset
```

`POST /reset` refuses while a run is in flight, and **never touches
`output/audit_trail.json`** — that file is append-only history across every run
(CC-OPS-31), and wiping it would destroy the record of what was reset.

A full three-ticket run takes roughly 10–15 minutes of live model calls. Each ticket runs
in its own child process under a 660s hard kill, so one wedged ticket cannot cost the
whole board.

### What a full run should produce

Tickets do not all close on the first pass, and that is the point. The agents queue
actions and stop; a human approves; a second pass closes the tickets. On the recorded
run that gave:

```
starting              $3,400.00
  102  rent paid     -$2,400.00   (the only payment the $500 floor allows)
                     ───────────
ending                $1,000.00   = cash_accounts
```

Tickets 101 and 103 resolve by **decision and communication**, not fulfilment — invoice
#501 stays unpaid, so the apparel vendor stays blocked. See
`output/desk_tickets.html` (Cash tab) and `output/resolved_tickets.json`.

### Portability note

`.mcp.json` holds **absolute paths** to this machine's venv and server script, because
that is the format the vibe coder reads. Running this elsewhere means editing those two
paths.

---

## The data

`data/campus_customs.db` is the original and is never written to.
`data/campus_customs_new.db` is the working copy; reset it with
`./.venv/bin/python backend/reset_db.py` or `POST /reset`.

The shop's "today" is **2026-08-31**, read from the `desk` table. Every due-date and
overdue calculation anchors there, never to the system clock.

**The board is one problem, not three.** $3,400 in checking against $2,400 rent and an
$840 overdue invoice. Paying both leaves $160 — below the $500 reserve floor — and the
vendor owed that $840 is the shop's only apparel supplier, so until it is paid neither
product ticket can restock. Every ticket runs into the same decision.

---

## The agents

Boss routes and alone closes tickets · Inventory counts stock by `(sku, size)` ·
Accounting watches cash and margins · Facilities keeps the lease · Customer Service
drafts letters and never sends.

Fully connected — every agent carries `ask_teammate`, and specialist-to-specialist
hand-offs happened on all three tickets. Prompts are in `backend/prompts/`, one per
agent, each including `shop_rules.md` verbatim so no agent can hold a different view of
policy.

## The rules

36 rules in `backend/prompts/shop_rules.md`, `CC-OPS-#`. The ones that did real work:

- **CC-OPS-1** — no agent moves money. `approve_pending` is withheld from every agent's
  toolset *and* the server refuses any agent name as the approver.
- **CC-OPS-2** — $500 reserve floor, checked when a payment is prepared and again when
  it is approved.
- **CC-OPS-35** — a vendor owed money will not ship.
- **CC-OPS-36** — cash only leaves; the balance can never go negative.

---

## Output

| File | |
|---|---|
| `output/harness.md` | the working document — tables, tools, agents, routes, dashboard, safety |
| `output/desk_tickets.html` | plan vs. actual per ticket, the cash ledger, the reflection |
| `output/resolved_board.html` | the resolved board with a screenshot per ticket |
| `output/resolved_tickets.json` | per-ticket outcome, contributions, approvals, cash check |
| `output/audit_trail.json` | append-only JSONL, every agent-loop step across every run |
| `output/design.md` | why the dashboard looks the way it does |
| `output/mcp_smoke.json` | MCP tool tests with their database verification |
| `AI_prompts.md` | every prompt typed into the vibe coder |

Both HTML files are standalone — double-click them, no server needed.
