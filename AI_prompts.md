# AI Prompts — HW 5: Campus Customs Multi-Agent Operations

Log of the prompts typed into the vibe coder (Claude Code), one section per problem.
Prompts are recorded verbatim as typed.

---

## Setup — Project Kickoff

### Prompt 1

> Today we are working on Homework 5: Campus Customs Multi-agent Operations. In this homework Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board including customer orders, rent, unpaid bills, discount requests, or whatever else the shop has to handle. We are going to build three pieces that talk to each other. 1.) an MCP server 2.) a FastAPI backend with a multi-agent team, and 3.) a React dashboard so a human can watch the agents at work and approve requests. The agent team has full connectivity meaning that any agent may delegate tasks to any other agent for help. For this assignment we will build the following agents: 1.) Boss - who will read each ticket, decide who should work on it, and makes the final calls 2.) Inventory - who will check stock by SKU and size, spot shortfalls, and figure out which vendor can restock 3.) Accounting - watches cash and invoices, checks margins, and prepared payments or purchase orders for human approval 4.) Facilities -- handles the shop space side (including leases, rent, etc.) and then 5.) Customer Service - who will draft messages for customers. We are going to work problem by problem so do not go ahead. I will first give you a data zip and we have to unzip it so that we have data/campus_customs.db. This is the original shop database. Tables will include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices. The tools will update the database as tickets get resolved. We will use my PORTKEY_API_Key for AI calls. We will also ONLY use gpt-6-luna through Portkey for every agent. No other model should show up in my code or runs. We will work one problem at a time, do not go ahead at any point. Are you rready to begin? I wioll give you problem 1 if so

### Prompt 2

> is gpt-6-luna different tthan gpt5-6-luna?

**Why a second prompt was needed:** The first prompt named the model as `gpt-6-luna` while the project's `AGENTS.md` specified `gpt5-6-luna`, and I needed to know whether those were two different models before committing every agent in the project to one of them.

**Outcome:** Searched the course folder for every `*luna*` string. Found three spellings in use:
`gpt-5.6-luna` (what the Portkey gateway echoes back in HW 3's `output/audit_trail.json`),
`gpt5-6-luna` (used in `hw1/`, `HW 2/sales_agent.py`, `Lecture 3/app.py`, and `AGENTS.md`), and
`gpt-6-luna` (used in `Lecture 10/mult_agent_hp/` and `Lecture 11/mult_agent_hp_tokenomics/`).
All three resolve to the same underlying model through Portkey. Standardized on **`gpt-6-luna`**,
read from `MODEL_NAME` in the HW 5 `.env`, so the string appears in exactly one place in the code.

---

## Problem 1 — Vibe Coder Prompts

### Prompt 1

> Okay let's begin. Problem 1: vibe coder prompts. Create AI_prompts.md and keep it updated as we work. This file will be the log of what I type into the vibe coder. There will be one section for each problem. Each section must include 1.) the problem number and title. 2.) at least one prompt that I typed 3.) if a second prompt was needed, ask me to give you one sentence on what was lacking from the first that required a second prompt.

**Outcome:** Created `AI_prompts.md` with this structure. The file is updated at the end of each
problem as work proceeds.

---

## Problem 2 — Study the Campus Customs Database

### Prompt 1

> Problem 2: "Study the Campus Customs database" Now I am attaching the zip. Unzip it first and then open data/campus_customs so we can look through every table and its fields. Copy the original file to data/campus_customs_new.db (later problems will update that working copy. I want to look at the three open tickets and see how they link to other tables. Start output/harness.md. For each table, list the fields and one short line for why that table matters for the agents. We will keep growing this harness file in later problems.

**Outcome:** Extracted `data/campus_customs.db` from the zip (single-file archive, integrity check passed)
and copied it to `data/campus_customs_new.db` as the working copy. Walked all 9 tables (23 rows total),
traced the 3 open tickets through their joins, and wrote `output/harness.md` with per-table field lists,
a one-line "why it matters" for each, the ticket link-maps, and the shared cash constraint
($3,400 balance vs. $3,240 of obligations).

---

## Problem 3 — Build the MCP Server

### Prompt 1

> Problem 3: "Build the MCP server". Write an MCP service in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db. We do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. We will add more tools to it later but for now write three tools that we know we will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database. In output/harness.md, list each of the three MCP tools. Every tool should include: which table it reads, which ticket it helps unlock (101,102, or 103), and one sentence on why that tool is the right one for that ticket. Vague lines like "reads inventory" will score low when being graded by the professor so make sure it is good. Make sure to tie the tool to the ticket. Also, addd a short mcp_server/READSME.md file that eplains what the MCP server is for, which database file it uses, and the three tools it has. Understood?

**Outcome:** Created the project `.venv` and installed `fastmcp` (4.1.0). Wrote
`mcp_server/server.py` — a FastMCP server named `campus-customs-ops` reading
`data/campus_customs_new.db` read-only — with one tool per open ticket:
`check_stock` (101), `get_rent_obligation` (102), `check_discount_margin` (103).
Both no-invented-data rules are enforced in code: unknown keys return `found: false`
with valid options listed, and "today" is read from `desk.date_today` rather than the
system clock. Verified all three through the MCP layer against the real database.
Added `mcp_server/README.md`, `mcp_server/requirements.txt`, and a §4 section in
`output/harness.md` tying each tool to its ticket.

---

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompt 1

> Okay now for Problem 4: "Add the MCP server to the vibe coder and test each tool". Now I want to add the MCP server to this project so the vibe coder can call the tools. Save the connection JSON text in .mcp.json at the project root (or however my vibe cover saves local MCP server lists). With the vibe coder connected, test each of the three MCP tools. Save the evidence in output/mcp_smoke.json. For every tool include: 1.) the prompt I asked the vive coder 2.) the tool name 3.) the tool output (must match values in data/campus_customs_new.db). Is everything clear or do you have any questions? Let me know which tools you are going to select first for approval along with your reasoning.

### Prompt 2

> do i close out of claude and reoppen?

**Why a second prompt was needed:** The first prompt assumed the MCP server could be tested
immediately, but `.mcp.json` is only read when the vibe coder starts, so the tools were not yet
available in the running session and the restart step had to be clarified.

**Approved test prompts** (user approved running these rather than typing each one):

1. "Ticket 101 wants one Classic Bulldog Tee in size S. Do we have it in stock?"
2. "Ticket 102 is a rent notice on lease 1. How much is due, when, and can we cover it?"
3. "Ticket 103 wants 20 navy hoodies in M at 20% off list. What's the margin and is it above cost?"

**Outcome:** Wrote `.mcp.json` at the project root (stdio, absolute paths), verified it with a real
JSON-RPC handshake before connecting. After a full restart of the Claude desktop app the three tools
appeared as `mcp__campus-customs-ops__*`. Ran all three approved prompts, and every returned value
reconciled against `data/campus_customs_new.db` by independent SQL. Evidence saved to
`output/mcp_smoke.json`; summary added as §5 of `output/harness.md`. The database was unmodified
by the run (working copy still byte-identical to the original).

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompt 1

> Okay now for Problem 5: "Build the agent team and grow the MCP tools" For this we are going to build the agentic team for campus customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other will full connectivity. Put the agent prompts in backend/prompts/ -- one file per agent. Put data types in backend/models.py, and the agent files under backend/ (the layout can vary as long as the five roles are clear). Use my PORTKEY_API_Key and only gpt-6-luna as I previously states for every agent. We want the prompts that the agent needs to be as detailed as possible to cover all aspects of an agent's qwork and scope as this will score higher on the homework than a short, generic prompt. So once I give you the prompts let me know if you think I can improve them so that I ensure I score high on the homework. Add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts will come from the MCP server over data/campus_customs_new.db -- do not invent a second shop-tools layer that bypasses MCP. Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file and make sure to not wipe it each run. In output/harness.md, list each agent and each MCP tool (including ones I add in this problem) along with which table the tool uses. Also add a short safety section : the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what I have now. Can you give me a draft for the shop rules the agent needs that I can refine and approve?

### Prompt 2

> why is this taking so long?

**Why a second prompt was needed:** The first prompt did not say how long a live
multi-agent run should be allowed to take, and the first build had no cap on model
round-trips or request timeouts, so a run hung indefinitely and the pacing had to
be questioned before the missing limits were found and added.

**Approved policy decisions** (asked before building, answered by the owner):

- Cash reserve floor **$500** — chosen so the agents cannot clear both obligations
  alone and the human approval step is real rather than ceremonial.
- Student-organisation extra **5%** enabled, with Boss sign-off.
- **No agent auto-pay** at any threshold.

**Outcome:** Drafted `backend/prompts/shop_rules.md` (34 rules, `CC-OPS-#`) for approval
first, then built: five PydanticAI agents with full connectivity via a shared
`ask_teammate` tool, `backend/models.py`, five role prompts, `backend/agents/`
(config, audit, team), and `backend/run_ticket.py`. Grew the MCP server from 3 to 13
tools and added a `pending_approvals` queue table. Every agent uses `gpt-6-luna` only,
through Portkey. Audit trail appends JSONL to `output/audit_trail.json` — 289 entries
across 6 runs, never truncated. Ran all three tickets live. Added §6 and §7 to
`output/harness.md` and rewrote the tool list in `mcp_server/README.md`.

Two limits (CC-OPS-33 model round-trips, CC-OPS-34 deadlines) were added only after
a live run hung; and the ticket 103 run exposed a prompt gap — Boss quoted 20 units
without checking stock — which is recorded in the harness and fixed in `boss.md`.

---

### Prompt 3

> I realized I forgot to give a few initial. Rules of the shop I think. 1.) the field desk.date_today is "today" for the shop. Use this date to determine what is overdue. 2.) Vendor lead times come from the vendors table. 3.) A vendor will not ship new product while they still have an open unpaid invoice 4.) Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, made sure to update the relevant table. 5.) If there is not enough cash, the pay tool must refuse — no negative balances 6.) Cash only goes out in this homework — we did not model revenue, so no money comes in 7.) Before a full run to resolve the tickets, make sure to reset the database to the original values. 8.) Do NOT email customers or call real vendors. Drafts stay on the board. Is all of that clear and does it impact any of the work we've done so far

**Why a third prompt was needed:** The original Problem 5 prompt did not state the
shop's operating rules, so the build enforced only the constraints that were visible
in the data; four further rules — especially that a vendor will not ship while owed
money — had to be supplied before the agents could reason about the board correctly.

**Outcome:** Four of the eight rules (1, 2, 4, 8) were already enforced in code. Four
required changes: added `CC-OPS-35` (vendor shipping hold) with a new
`check_vendor_can_ship` tool, a hard refusal in `prepare_purchase_order`, and blocked
vendors sorted last in `find_vendor_for_sku`; added `CC-OPS-36` (cash is outflow-only,
absolute zero-balance guard independent of the policy floor); updated the Boss,
Inventory and Accounting prompts; and added `backend/reset_db.py`. MCP server grew to
14 tools, shop rules to 36.

Rule 3 changed the shape of the assignment: Bulldog Print Co is the only apparel
vendor and is owed $840, so neither product ticket can restock until invoice #501 is
paid — and that payment breaches the cash floor. The whole board now gates on one
human decision. The clean run confirmed the agents reason this way, with Boss,
Inventory and Accounting each independently calling `check_vendor_can_ship`.

---

### Prompt 4

> how do we improve that? or is there anything that can be done

**Why a fourth prompt was needed:** The third prompt's work left agent timeouts
occurring in roughly every run, and the cause had not been diagnosed — it needed an
explicit request to investigate whether the latency was fixable or inherent to the
endpoint.

**Outcome:** Measured the audit trail instead of guessing. Found latency was bimodal
(healthy calls 5–15s, wedged calls never return) and the slowest step was exactly
`90s × 3 retries` — the timeouts were caused by the retry setting, not the endpoint.
Also found `CC-OPS-29` (tool caching) had been declared but never implemented, so
every read tool ran three times per ticket.

Applied two fixes: `HTTP_TIMEOUT_S` 90s→45s with `max_retries` 2→1, and a
`CachingToolset` wrapper giving all five agents one per-run cache (write tools never
cached). Result on the same three tickets: wall clock **970.6s → 556.6s (−43%)**,
agent timeouts **4 → 0**, slowest step **271.4s → 90.6s**, 26 cache hits, correctness
unchanged.

The faster run then reached a decision path it had never reached before — a $500
partial payment — which exposed a real bug: `approve_pending` marked an invoice paid
on any amount, which would have silently unblocked the vendor under CC-OPS-35 while
$340 was still owed. Fixed so an invoice settles only when total payments cover it.

---

## Problem 6 — Plan the Three Tickets

### Prompt 1

> Okay now for Problem 6: "Plan the three tickets" For this one, before we wire the backend, I want to write down what I expect the team to do in each open ticket. Give me a draft of this so I can approve/amend it. Build output/desk_tickets.html -- a page I can double-click with one tab per ticket (101, 102, and 103. Also add empty Cash and Reflection tabs for later problems (but leave them blank or with a short "coming later" note for now). On each ticket tab, fill an Expected section only (leave room for an "Actual" section that we will fill later after we run the agents. For each ticket's Expected section, I need to write in my own words: 1.) who the boss cshould call first and why, all the agent delegations I expect - not "Boss calls everyone", and which MCP tools you expect that run to use. Draft these for me and then I will edit/approve if needed. Plans that send every specialist on every ticket will receive a low score on the homework so make sure not to do that. We will compare this plan to what actually happens when the agents resolve the three tickets. Understood?

### Prompt 2

> what do you think I should do/add

**Why a second prompt was needed:** The first prompt specified the structure of the plan
but not how the plan would be judged against the run, so the draft read as narrative and
had no mechanical way to be scored; a second prompt was needed to decide what to add to
make the comparison objective.

**Outcome:** Built `output/desk_tickets.html` — standalone, double-clickable, five tabs
(101, 102, 103, Cash, Reflection), blue/green theme, keyboard-navigable. Expected filled
on each ticket tab, Actual left as an empty placeholder. Deliberately restrained
delegation plan: **8 delegations total, no ticket uses all five agents**, with the
not-called agent named and justified on every ticket.

| Ticket | Boss calls first | Delegations | Not called |
|---|---|---|---|
| 101 | inventory | 3 | facilities |
| 102 | facilities | 2 | inventory, customer_service |
| 103 | accounting | 3 | facilities |

Then added three things on the second prompt: a **prediction scorecard** per ticket
(31 falsifiable checks total), a **board-level prediction** covering all three tickets
as one cash problem, and a **provenance note** stating plainly that the tickets had
already been run once in Problem 5, so this is an informed plan rather than a blind
prediction. Two specialist→specialist edges are planned (`inventory→accounting` on 101,
`facilities→accounting` on 102) to exercise the mesh rather than routing everything
through Boss. Approved as drafted.

---

## Problem 7 — Backend Routes

### Prompt 1

> Great — now for Problem 7: "Backend routes". My React frontend dashboard (which will come in the next problem) will need a backend it can call. In backend/main.py, use FastAPI and add routes that do the following: a.) Return the three tickets and whether each is open or resolved b.) Take a ticket id and run the agent team on that ticket c.) Return recent agent events - what each agent said and which tools they used - so the board can refresh d.) Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash e.) Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash f.) Return the current checking balance from cash_accounts g.) Reset the database to the original values when you want to try a fresh run. From the backend/folder, start the server with uvicorn main:app --reload --port 8000. This will turn on the backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what URL/what it does). Does that all make sense? If so, then go.

### Prompt 2

> sorry i accidentally duplicated one you're right, there should have only been a-f and not the duplicated d and e

**Why a second prompt was needed:** Items (d) and (e) in the first prompt were identical,
so it was ambiguous whether two distinct approval routes were wanted or one had been
duplicated by accident; the second prompt confirmed it was a duplicate.

**Outcome:** Built `backend/main.py` with FastAPI — 12 routes covering a–g as one
approval route plus `GET /approvals` (a dashboard cannot approve what it cannot list),
`/health`, `/runs` and `/runs/{id}`. All shop facts and shop changes go through the MCP
server; `/reset` is the only exception, being a file operation rather than a shop fact.
`POST /tickets/{id}/run` returns a `run_id` in ~1s instead of blocking for the minutes a
live run takes, and the dashboard follows progress via `GET /events?since=`.

Verified against the live server: approval with a blank name → 400; $2,400 rent approved
→ cash $3,400→$1,000 with the person's name recorded; $500 partial on the $840 invoice →
invoice stays open, vendor stays blocked; full invoice afterwards → **409** with cash
unchanged; concurrent run on one ticket → 409; reset during a run → 409.

Testing caught one bug: after a partial payment `check_vendor_can_ship` still reported
the invoice's face value ($840) rather than the $340 outstanding — the figure shown to
the person deciding what it would cost to unblock the vendor. Fixed.

Also closed the known duplicate-draft defect here, since this is where the approval
queue becomes something a person reads: `prepare_customer_message` now returns the
existing pending draft for a ticket instead of queueing a second one.

---

## Problem 8 — Agent Dashboard

### Prompt 1

> In Problem 8: "Agent dashboard" we will build the frontend dashboard with React + Site + Typescript. The page should call the routes we built in Problem 7. At minimum the board should: a.) List all three tickets b.) Let you pick one ticket and start the agent team on it c.) Show each agent and what they are saying / doing while the ticket runs d.) Mark a ticket resolved when the run finishes e.) Show a short summary of what each agent did on the that ticket f.) Let a human approve a pay or purchase when asked g.) Show the checking balance (it should drop after an approved pay). Make the dashboard look good. I will get extra points on my bonus for a more creative layout and feel. Use similar design styles and animations as Homework 4 maybe and let me know other ideas you have to increase the creativity. This is a real desk people would want to sit at, so make sure to put a lot of effort in how it looks. Tell the front end to talk to the backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev. This opens the React desk in the browser so you can pick tickets and watch agents. Write output/design.md with what was chosen for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why — including the creative choices that make it feel specialist and something humans would actually enjoy using.

**Outcome:** Built `frontend/` — React 19 + Vite + TypeScript, no UI library, all
styling hand-written. Carried HW 4's 1936 game-day palette and typefaces forward and
reframed them as **the back office of that same shop**: a dispatcher's desk with a wire
tray, five staff, and a cash drawer on green felt.

Layout is a three-column desk — in-tray → floor and wire → your desk — so work reads
left to right. Each agent gets its own **stationery** (typeface, paper, colour) rather
than a colour-coded dot, so a wall of events is scannable without a legend. Delegations
are drawn as ink threads between desks with **refused hand-offs as broken red dashes**,
making the fully connected mesh visible including when a rule correctly denies it. The
cash drawer **counts down and flashes crimson only when falling**, encoding CC-OPS-36 in
the motion. A 409 refusal renders in place as a stamped explanation rather than an error.
Handsome Dan carries over from HW 4, asleep under the desk and waking when the team runs.

Verified live against a real ticket-101 run. `output/design.md` records the layout,
how the agents read differently, how resolved tickets and cash show up, and ten named
creative choices.

---

## Problem 9 — Resolve the Tickets

### Prompt 1

> Now for Problem 9: "Resolve the tickets". Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so that we can start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run: which agents worked, what they delegates, and which tools they used. Keep the Expected section so I can then compare the two. On the Cash tab of the same output/desk_tickets.html, itemize the money: a.) starting checking balance (after the reset) b.) For each ticket: how cash changes that ticket resolved, and why (which pay/dollar amount) c.) Ending checking balance - it must match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. Also make sure to save a.) output/resolved_tickets.json — for each ticket: id, final status, short outcome, what each agent contributed and any human approvals b.) output/resolved_board.html — a page that can be double-clicked with a screenshot of the React board for each resolved ticket (101, 102, and 103). Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

**Outcome:** Reset the working database ($3,400.00 starting balance, recorded), then ran
all three tickets to resolution across 9 runs appended to `output/audit_trail.json`.

**All three resolved. Ending balance $1,000.00, reconciled against `cash_accounts`.**
Only ticket 102 moved money (−$2,400 rent, payment #1, approved by a named human).
Invoice #501 was deliberately deferred — rent ranks first under CC-OPS-3 and paying both
would breach the $500 floor with no inbound cash under CC-OPS-36 — so Bulldog Print Co
stayed blocked and tickets 101 and 103 resolved by decision and communication rather than
fulfilment.

Filled the Actual sections in `output/desk_tickets.html` with per-ticket agents,
delegations, tools and a HIT/MISS scorecard against the Problem 6 plan; itemised the
money on the Cash tab. Wrote `output/resolved_tickets.json` (generated from the database
and audit trail, with a programmatic cash check) and `output/resolved_board.html` with an
embedded screenshot of the React board per resolved ticket. Finished `output/harness.md`
with §14 (the run) and §15 (a complete index of tables, tools, agents, routes, dashboard
and safety rules).

Two defects surfaced and were fixed: Boss once reported `ticket_closed: true` after its
tool budget withdrew `close_ticket` before it could call it — the structured output is the
agent's claim, the database is the truth — and each re-run of ticket 103 queued a fresh
customer message that then blocked the close, so deduplication now counts approved
messages, not just pending ones. The dashboard also gained run-history loading so a
resolved ticket can be reviewed rather than showing a blank wire.

---

### Prompt 2

> are there any other fixes we need to make?

**Why a second prompt was needed:** The first prompt asked for the full run and its
artefacts but not for a review of the finished system, so defects that no longer blocked
the run — including a hole in the human-approval rule — would otherwise have gone unexamined.

**Outcome:** Audited the finished system rather than assuming it was sound. The frontend
production build was clean and the API key was properly gitignored and outside the project,
but two real defects surfaced, both the same mistake — a rule enforced in the wrong layer.

`approve_pending` rejected a blank approver but **accepted `"boss"`**, writing a payment row
and debiting cash. It had never mattered because the backend filters the tool out of every
agent's toolset, but that is a client-side guarantee and the MCP server answers any client.
The server now refuses every agent name itself. And rejecting an approval left no trace on
the ticket, so a ticket could close as though the action had never been proposed; rejection
now annotates the ticket's notes.

Also corrected a stale description of the draft-deduplication fix and added
`tsconfig.tsbuildinfo` to the frontend gitignore. Verification side effects were cleaned up
and the true Problem 9 end state restored: three tickets resolved, one payment, cash
$1,000.00 reconciling against `cash_accounts`.

---

## Problem 10 — Reflection

### Prompt 1

> Now for Problem 10: "Reflection" Open output/desk_tickets.html and fill the Reflection tab. In my own words I need to give a detailed and thorough answer for the following: How would I evaluate the performance of the agents on each ticket and why? For each ticket, how did Actual compare to the Expected plan we wrote earlier? What would have been simpler as one agent with tools -- and why? Describe three new problems Campus Customs might face that this agent team could solve with the tools we built. Describe three new problems Campus Customs might face that this agent team could not solve with the tools we built, and explain the tools and agents we'd need to solve them. I have to tie every answer to this app and the three tickets we ran -- using the tickets tab and Cash tab on the same page as our evidence. Generic AI essays without Campus Customs details will score low so make sure that's not the case. Give me detailed, thorough responses as a draft to review and edit for the reflection. Does that make sense?

**Outcome:** Filled the Reflection tab in `output/desk_tickets.html` with all five answers,
every claim grounded in the measured run rather than asserted. Pulled the real per-ticket
figures from the audit trail first (101: 2 runs / 20 model calls / 3 delegations; 102: 2 runs
/ 15 / 2; 103: 5 runs / 61 / 10) so the evaluation rests on evidence.

Specific positions taken, all tied to Campus Customs rather than generic:

- **Evaluation** rejects "did it close" as a measure — all three closed and the performances
  were not equal. Proposes runs-to-resolution, promises-not-supported-by-data, and
  cash-moved-without-a-human instead.
- **Plan vs actual** concedes the plan was wrong about ticket 103's price: it predicted $46.40
  on 20 units from the ladder, while Boss quoted $55.10 on the 8 units actually in stock
  because a volume tier cannot apply to quantities it can't supply.
- **One agent vs five** argues honestly that most of this board would have been simpler as a
  single agent with the fourteen tools — ticket 102's delegations moved a question to an agent
  with no extra capability — while naming where the five genuinely earned their keep.
- **Three solvable problems** use real rows: `CC-MUG-CREST` is also at qty 0, and unlike
  Bulldog, Elm City Gifts is owed nothing so `check_vendor_can_ship` returns true.
- **Three unsolvable problems** each trace to a missing direction of movement — refunds (no
  inbound cash under CC-OPS-36, no returns table), receiving goods (our own `approve_pending`
  note admits inventory is never incremented), and anything future-dated (the shop clock is
  frozen, so the team cannot see that next month's rent exceeds the closing balance).

---

### Prompt 2

> is there anything else I should improve to make sure I score high on the homework

**Why a second prompt was needed:** The first prompt asked for the reflection content but not
for a check that the submission as a whole met every earlier requirement, so gaps outside the
reflection — including an unfilled field required by the Problem 1 rules — would have gone
unnoticed.

**Outcome:** Audited the whole submission against the stated requirements rather than the
reflection alone. Found three gaps: the Setup section still carried an unfilled
`_(pending)_` for the "why a second prompt was needed" field that Problem 1 requires (now
filled); there was no `README.md`, so nothing told a reader how to run the three pieces or in
what order (written, including the note that `.mcp.json` holds absolute paths and needs editing
on another machine); and there was no `.env.example`, so nothing documented that
`PORTKEY_API_KEY` and `MODEL_NAME` are the two knobs (written). Also removed a stray
`tsconfig.tsbuildinfo` build artefact and added it to the frontend gitignore.

---

## Problem 11 — Submit to GitHub

### Prompt 1

> Problem 11: "Submit to Github". Push the code to a public Github repository so graders can clone it. I am then going to submit it to Canvas. It should also be put in output/github_url.txt. I do not want to push my real .env to the Github repo. Do include both database files under data/ (the original and the working copy) so graders can run the app easily. The expected file layout is in the screenshot. README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.

**Outcome:** Pushed to **https://github.com/kelly-enright/campus-customs-hw5** (public),
matching the existing `campus-customs-hw4` naming convention. 57 files in one commit.

Restructured to match the layout in the screenshot: renamed `mcp_server/mcp_server.py` to
`mcp_server/server.py` and updated every reference to it, and consolidated
`backend/requirements.txt` and `mcp_server/requirements.txt` into a single root
`requirements.txt`.

Rewrote the README's run section as six numbered steps covering everything asked for:
install, set the key, **copy the original database over the working copy for a clean run**,
start the MCP server (noting the backend launches it over stdio, so it is only needed
standalone), start the FastAPI backend, start the React board — plus a separate section on
**resetting before a full three-ticket run** and what a correct run should produce.

Secret safety was checked three times rather than assumed: the live key was grepped against
every file in the folder, then against every staged file's contents individually, and the
audit trail's field names were checked for anything credential-shaped. All clean. `.env` is
gitignored and absent; `.env.example` documents the two variables.

Verified by cloning the public repo fresh into a scratch directory: 57 files, no `.env`,
both databases present and opening correctly — `campus_customs.db` with 9 tables, $3,400 and
three open tickets, and `campus_customs_new.db` with 10 tables, $1,000 and three resolved —
so a grader can inspect the finished state and reset to a clean board from the same clone.
`output/github_url.txt` holds the URL and clone instructions.

---

