# Campus Customs — Agent Harness

Working notes on the shop database and the problems the agent team has to solve.
This file grows with each problem.

- **Original (read-only reference):** `data/campus_customs.db`
- **Working copy (tools write here):** `data/campus_customs_new.db`
- **Shop "today":** `2026-08-31` (from the `desk` table — agents should treat this as the current date, not the wall clock)

---

## 1. Tables

Nine tables, 23 rows total. Small on purpose — every row matters.

### `desk` — 1 row
| Field | Type | |
|---|---|---|
| `date_today` | TEXT | `2026-08-31` |
| `notes` | TEXT | empty |

**Why it matters:** Defines "today" for the whole simulation. Every due-date, overdue, and lead-time calculation an agent makes has to anchor here or the answers drift.

### `tickets` — 3 rows, all `open`
| Field | Type | |
|---|---|---|
| `id` | INTEGER | PK |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | who asked |
| `subject` | TEXT | one-line summary |
| `sku`, `size`, `qty` | TEXT/TEXT/INT | product request (nullable) |
| `lease_id` | INTEGER | FK → `leases.id` (nullable) |
| `invoice_id` | INTEGER | FK → `invoices.id` (nullable) |
| `status` | TEXT | `open` |
| `notes` | TEXT | free text |
| `created_at` | TEXT | ISO-8601 w/ offset |

**Why it matters:** This is the board. Boss reads it, routes it, and closes it; `type` is the routing signal and the nullable FK columns say which other tables the ticket reaches into.

### `inventory` — 10 rows
| Field | Type | |
|---|---|---|
| `sku`, `size` | TEXT | composite PK |
| `name` | TEXT | display name |
| `qty` | INTEGER | units on hand |
| `location` | TEXT | aisle |

**Why it matters:** Inventory's primary table — stock is tracked per `(sku, size)`, so a SKU being "in stock" says nothing until you pick a size.

### `pricing` — 4 rows
| Field | Type | |
|---|---|---|
| `sku` | TEXT | PK |
| `unit_cost` | REAL | what the shop pays |
| `list_price` | REAL | what the customer pays |

**Why it matters:** Accounting's margin floor. Any discount Boss approves gets checked against `unit_cost` here.

### `vendors` — 3 rows
| Field | Type | |
|---|---|---|
| `id` | INTEGER | PK |
| `name` | TEXT | |
| `specialty` | TEXT | `apparel reprint`, `mugs and small goods`, `local courier` |
| `lead_days` | INTEGER | 5 / 3 / 1 |

**Why it matters:** Restock routing. There's no SKU→vendor foreign key, so an agent has to match the product to `specialty` by judgment — apparel SKUs go to Bulldog Print Co, mugs to Elm City Gifts.

### `leases` — 1 row
| Field | Type | |
|---|---|---|
| `id` | INTEGER | PK |
| `space_name`, `landlord` | TEXT | Chapel Street shop / Elm City Properties |
| `monthly_rent` | REAL | 2400.00 |
| `next_due` | TEXT | `2026-09-02` |
| `notes` | TEXT | empty |

**Why it matters:** Facilities' table. Rent is the single largest claim on cash, and `next_due` vs. `desk.date_today` is what makes it urgent.

### `cash_accounts` — 1 row
| Field | Type | |
|---|---|---|
| `name` | TEXT | PK — `checking` |
| `balance` | REAL | 3400.00 |
| `date` | TEXT | `2026-08-31` |

**Why it matters:** One account, one balance — the hard constraint. Every proposed payment competes for this number, so Accounting can't treat tickets independently.

### `invoices` — 1 row
| Field | Type | |
|---|---|---|
| `id` | INTEGER | PK |
| `vendor_id` | INTEGER | FK → `vendors.id` |
| `amount` | REAL | 840.00 |
| `due_date` | TEXT | `2026-08-28` |
| `status` | TEXT | `open` |
| `description` | TEXT | "Rush reprint CC-TEE-WHITE S" |

**Why it matters:** What the shop owes. Invoice 501 is already **3 days overdue** as of the desk date, and it's tied to the restock that ticket 101 depends on.

### `payments` — 0 rows
| Field | Type | |
|---|---|---|
| `id` | INTEGER | PK |
| `kind` | TEXT | e.g. rent / invoice |
| `ref_id` | INTEGER | points at a lease or invoice — untyped, no FK |
| `amount` | REAL | |
| `account` | TEXT | → `cash_accounts.name` |
| `paid_at` | TEXT | |
| `approved_by` | TEXT | **human approver** |

**Why it matters:** The audit trail, and it starts empty — every row here is something the agents did. `approved_by` is where human-in-the-loop approval gets recorded, so nothing should land here without a person signing off.

---

## 2. The three open tickets

### Ticket 101 — `customer_order` — Tauhid Zaman, "Bulldog tee"
Wants 1 × `CC-TEE-WHITE` size **S**.

| Link | Finds |
|---|---|
| `sku`+`size` → `inventory` | **qty = 0** — stockout |
| `sku` → `pricing` | cost 8.00, list 28.00 |
| `invoice_id` → `invoices` | #501, $840, due 2026-08-28, **open/overdue** |
| `invoices.vendor_id` → `vendors` | Bulldog Print Co, 5 lead days |

The catch: the one size the customer wants is the one size at zero, and the reprint that would fix it is sitting on an unpaid overdue invoice. Restocking and paying the bill are the same problem.

### Ticket 102 — `rent_notice` — Elm City Properties, "Rent due"
| Link | Finds |
|---|---|
| `lease_id` → `leases` | #1, Chapel Street shop, $2,400/mo, due 2026-09-02 |
| (implicit) → `cash_accounts` | checking $3,400 |

Due in **2 days**. Affordable alone, but see below.

### Ticket 103 — `price_override` — Yale AI Club, "Bulk hoodie discount"
Wants 20 × `CC-HOOD-NAVY` size **M**, asking for a bulk discount.

| Link | Finds |
|---|---|
| `sku`+`size` → `inventory` | have 8, **short 12** |
| `sku` → `pricing` | cost 22.00, list 58.00 → 62.1% margin |
| (implicit) → `vendors` | apparel reprint = Bulldog Print Co, 5 lead days |

At list: $1,160 revenue on $440 cost. The discount has room, but the 12-unit shortfall needs a 5-day reprint and the vendor is the same one that's owed $840.

---

## 3. The tension the agents have to find

| | |
|---|---|
| Cash in checking | **$3,400** |
| Open invoices (#501, overdue) | − $840 |
| Rent due in 2 days | − $2,400 |
| **Remaining** | **$160** |

The three tickets aren't independent — they all draw on one $3,400 balance, and clearing all of them leaves $160. Any agent that resolves a ticket in isolation will approve something the shop can't afford. That's the case for the Boss having final say and for human approval on anything that moves money.

Two more things an agent has to infer rather than read:
- **No SKU→vendor key.** Restock routing comes from matching the product against `vendors.specialty`.
- **`payments.ref_id` is untyped.** It points at a lease *or* an invoice depending on `kind`, with no foreign key to enforce it — tools will have to keep that honest.

---

## 4. MCP tools (Problem 3)

Server: `mcp_server/server.py` (FastMCP, named `campus-customs-ops`).
Reads the working copy `data/campus_customs_new.db`. All three tools are
read-only; write tools come later.

Every agent on the team calls these rather than touching SQLite, so there is one
definition of what the shop knows. Two invariants are enforced inside the tools:
values are only ever columns or arithmetic over columns (unknown keys return
`found: false` with the valid options, never a guess), and "today" is read from
`desk.date_today` rather than the system clock.

### `check_stock(sku, size=None, qty_needed=None)` → unlocks **Ticket 101**

- **Reads:** `inventory` — specifically the `(sku, size)` composite primary key, returning `qty`, `location`, and a per-size breakdown of the SKU.
- **Ticket:** 101 — Tauhid Zaman wants 1 × `CC-TEE-WHITE` in size **S**.
- **Why this tool for this ticket:** Ticket 101 names a size, and `inventory` stores quantity per `(sku, size)` — a SKU-only lookup on `CC-TEE-WHITE` returns 10 units across S/M/L/XL and would read as "we can ship it," when size S is precisely the row sitting at **0**; `check_stock` queries the exact pair the ticket names and returns `shortfall: 1`, which is what converts 101 from a pick-and-pack into a restock problem.
- **Verified against the DB:** `check_stock("CC-TEE-WHITE", "S", 1)` → `qty_on_hand: 0`, `in_stock: false`, `shortfall: 1`, `can_fulfill_from_stock: false`.

### `get_rent_obligation(lease_id)` → unlocks **Ticket 102**

- **Reads:** `leases` (joined on `tickets.lease_id`) for `monthly_rent`, `next_due`, and `landlord`; `desk.date_today` to date the deadline; `cash_accounts.balance` to test coverage.
- **Ticket:** 102 — Elm City Properties, rent notice on lease 1.
- **Why this tool for this ticket:** Ticket 102 carries `lease_id = 1` and no dollar figure at all, so the $2,400 and the 2026-09-02 due date can only come from the `leases` row; the tool then measures that date against the shop's today (**2 days out**, not yet late) and against the **$3,400** checking balance in a single call, so Facilities and Accounting reason from one shared coverage number instead of Facilities scheduling rent that Accounting cannot fund.
- **Verified against the DB:** `get_rent_obligation(1)` → `monthly_rent: 2400.0`, `days_until_due: 2`, `is_overdue: false`, `cash_covers_rent: true`, `cash_after_paying_rent: 1000.0`.

### `check_discount_margin(sku, qty, proposed_unit_price=None)` → unlocks **Ticket 103**

- **Reads:** `pricing` — `unit_cost` and `list_price` for the SKU, with revenue, cost of goods, gross profit, and margin computed over the ticket's `qty`.
- **Ticket:** 103 — Yale AI Club wants 20 × `CC-HOOD-NAVY` size M at a bulk discount.
- **Why this tool for this ticket:** Ticket 103 asks for a discount without naming a price, and a discount is only answerable against `unit_cost` ($22) rather than `list_price` ($58) — so the tool returns the 62.1% list margin, the **$22 break-even floor** below which the shop loses money per hoodie, and, for any price Boss floats, the resulting margin and total profit across all 20 units; that is what lets Accounting tell Boss how deep a discount the shop can actually sign rather than guessing at a percentage.
- **Verified against the DB:** `check_discount_margin("CC-HOOD-NAVY", 20, 46.40)` → 20% off list, `gross_profit: 488.0` (vs. `720.0` at list), `margin_pct: 52.6`, `above_cost: true`.

### Coverage note

The three tools answer one ticket each, but they do not yet resolve the cash
contention in §3 — `get_rent_obligation` reports the balance against rent alone
and does not see invoice #501. Reconciling competing claims on the same $3,400 is
Boss's job plus the write tools still to come.

---

## 5. MCP connection and smoke test (Problem 4)

Connection JSON lives at `.mcp.json` in the project root, matching the course
convention from `Lecture 9/.mcp.json` — stdio transport, absolute paths to the
HW 5 venv Python and the server script:

```json
{
  "mcpServers": {
    "campus-customs-ops": {
      "command": ".../HW 5/.venv/bin/python",
      "args": [".../HW 5/mcp_server/server.py"]
    }
  }
}
```

The server is only read at vibe-coder startup, so a full restart of the Claude
desktop app was needed before the tools appeared. Once connected they are
namespaced `mcp__campus-customs-ops__<tool>`.

All three tools were called by the vibe coder and every value reconciled against
`data/campus_customs_new.db` by independent SQL. Evidence: `output/mcp_smoke.json`.

| Ticket | Tool | Key result | DB match |
|---|---|---|---|
| 101 | `check_stock` | size S `qty_on_hand: 0`, `shortfall: 1` | yes |
| 102 | `get_rent_obligation` | $2,400 due 2026-09-02, `days_until_due: 2`, $1,000 left | yes |
| 103 | `check_discount_margin` | 20% off → 52.6% margin, $488 profit, above the $22 floor | yes |

Two things the run confirmed beyond "the tools return data":

- **The shop clock holds.** The test ran on 2026-10-12 while the shop's date is
  2026-08-31. `get_rent_obligation` returned `days_until_due: 2`; a system-clock
  read would have reported rent ~40 days overdue and poisoned every downstream
  decision.
- **The tools are genuinely read-only.** After the run,
  `data/campus_customs_new.db` is still byte-identical to `data/campus_customs.db`.
  The working copy is clean for the write tools still to come.

---

## 6. The agent team (Problem 5)

Five PydanticAI agents, **fully connected**: every agent carries the same
`ask_teammate` tool, so any agent may delegate to any other. Boss is the entry
point and the only agent that may close a ticket, but it is not a relay — in the
ticket 101 run, Accounting asked Facilities directly without going through Boss.

Every agent uses **`gpt-6-luna` through Portkey** and nothing else. The model name
appears once, in `backend/agents/config.py`, read from `MODEL_NAME`.

| Agent | Scope | Prompt | Typically calls |
|---|---|---|---|
| **boss** | Reads the board, routes, arbitrates, decides, closes tickets | `backend/prompts/boss.md` | `list_open_tickets`, `get_cash_position`, `close_ticket` |
| **inventory** | Stock by SKU+size, shortfalls, par levels, restock routing | `backend/prompts/inventory.md` | `check_stock`, `find_vendor_for_sku` |
| **accounting** | Cash, invoices, margins, discount ladder, payment prep | `backend/prompts/accounting.md` | `get_cash_position`, `list_open_invoices`, `check_discount_margin`, `prepare_payment`, `prepare_purchase_order` |
| **facilities** | Leases, rent, landlords, the space | `backend/prompts/facilities.md` | `get_rent_obligation` |
| **customer_service** | Drafting messages to customers and requesters | `backend/prompts/customer_service.md` | `check_stock`, `prepare_customer_message` |

All five prompts include `backend/prompts/shop_rules.md` verbatim, so no agent
can hold a different view of policy than another.

### MCP tools and the tables they use

Fourteen tools, all on the one server in `mcp_server/`. The agents reach them
through `load_mcp_toolsets(".mcp.json")` — the same config file the vibe coder
uses, so there is exactly one tools layer.

| Tool | Tables | R/W | Unlocks |
|---|---|---|---|
| `list_open_tickets` | `tickets`, `desk` | read | the board; entry point for every run |
| `check_stock` | `inventory` | read | 101, 103 |
| `get_rent_obligation` | `leases`, `desk`, `cash_accounts` | read | 102 |
| `check_discount_margin` | `pricing` | read | 103 |
| `get_cash_position` | `cash_accounts`, `invoices`, `leases`, `pending_approvals`, `desk` | read | **cross-ticket** — the only view of competing claims |
| `list_open_invoices` | `invoices`, `vendors`, `desk` | read | 101 (invoice #501) |
| `find_vendor_for_sku` | `vendors`, `inventory`, `desk` | read | 101, 103 (restock routing) |
| `check_vendor_can_ship` | `vendors`, `invoices`, `desk` | read | **101, 103** — a vendor owed money refuses new orders (CC-OPS-35) |
| `list_pending_approvals` | `pending_approvals` | read | avoids queueing the same action twice |
| `prepare_payment` | writes `pending_approvals`; reads `invoices`, `leases`, `cash_accounts` | write | 101, 102 |
| `prepare_purchase_order` | writes `pending_approvals`; reads `vendors`, `pricing`, `inventory` | write | 101, 103 |
| `prepare_customer_message` | writes `pending_approvals`; reads `tickets` | write | 101, 103 |
| `approve_pending` | writes `payments`, `cash_accounts`, `invoices`, `pending_approvals` | write | **human only — withheld from agents** |
| `close_ticket` | writes `tickets`; reads `pending_approvals` | write | all |

`pending_approvals` is a table this problem adds to the working copy. It is the
approval queue: everything an agent prepares waits there with the rule that sent
it, until a person decides.

### What the ticket 101 run actually did

Run `61da3e98e61e`, 63 audit entries, 20 tool calls, 318s.

- Boss read the board, checked cash **before** promising anything, then asked
  Inventory and Accounting in parallel.
- Accounting asked **Facilities directly** (depth 2) — full connectivity, not a star.
- Facilities tried to ask Accounting back; **refused by CC-OPS-27** (cycle).
- Customer Service **timed out**; Boss degraded gracefully, drafted the message
  itself, and said so in its reasoning rather than hiding the gap.
- Final decision surfaced the cash conflict with the arithmetic and **two options**,
  exactly as CC-OPS-4 requires: `$3,400 − $2,400 − $840 = $160`, $340 below the floor.
- Ticket left **open** because a draft was pending. Cash **unchanged at $3,400**,
  `payments` still **empty**.

That last line is the one that matters: a full agent run touched real money
tables and moved nothing, because only a human can.

---

## 7. Safety and cost control

### Guardrails a real business would want

| Guardrail | Rule | How it is enforced |
|---|---|---|
| Agents never move money | CC-OPS-1 | `approve_pending` is filtered out of every agent's toolset in code; `prepare_*` only ever writes to the approval queue |
| A real person is named on every payment | CC-OPS-1 | `approve_pending` rejects a blank or missing `approved_by`; `payments.approved_by` is never written by an agent |
| The shop cannot be drained | CC-OPS-2 | $500 floor checked when a payment is **prepared** and re-checked when it is **approved**, because the balance moves in between |
| Nothing urgent gets silently dropped | CC-OPS-4 | Unfundable obligations are returned as `blocked_by_floor` with the arithmetic, forcing escalation |
| No sale below cost | CC-OPS-8, CC-OPS-9 | `check_discount_margin` returns the margin floor and cost floor as explicit booleans |
| No invented facts | CC-OPS-5, CC-OPS-20 | Unknown keys return `found: false` with valid options; PO cost comes from `pricing`, never from the agent |
| No invented dates | CC-OPS-21 | "Today" is `desk.date_today`; the system clock is never read |
| A vendor owed money will not ship | CC-OPS-35 | `prepare_purchase_order` **refuses outright**; `find_vendor_for_sku` sorts blocked vendors last and returns `restock_blocked` |
| The balance can never go negative | CC-OPS-36 | absolute zero check in `prepare_payment` and `approve_pending`, independent of the editable policy floor |
| No imaginary funding options | CC-OPS-36 | `get_cash_position` returns `cash_is_outflow_only`; prompts forbid offering "raise more cash" |
| Customers are never contacted by a bot | CC-OPS-16 | Messages are queued as drafts; there is no send tool |
| Unfinished work cannot be hidden | CC-OPS-1 | `close_ticket` refuses while any approval on that ticket is pending |
| Every action is auditable | CC-OPS-31 | Append-only JSONL trail with run id, agent, tool, args, rules checked, and timing |

### Limits that keep token use in check

| Limit | Rule | Value | Enforcement |
|---|---|---|---|
| Delegations per ticket | CC-OPS-25 | 10 | counted in `TeamDeps`; refused at the tool |
| Delegation depth | CC-OPS-26 | 3 | computed per chain; refused at the tool |
| Repeat / cyclic delegation | CC-OPS-27 | — | `asked_pairs` set + chain walk; **fired in the live run** |
| MCP tool calls per agent | CC-OPS-28 | 8 | the toolset **filter stops offering tools**, so the agent answers from what it has instead of crashing |
| Model round-trips per agent | CC-OPS-33 | 10 | `UsageLimits(request_limit=...)`, caught and degraded to a partial answer |
| Deadlines | CC-OPS-34 | 90s request / 120–600s agent by depth / 600s ticket | `asyncio.timeout` + an HTTP timeout on the client |
| Trace size | CC-OPS-30 | 600 chars | `audit.clip()` |

Two of these were added only after a live run exposed the gap, which is worth
recording honestly:

- **CC-OPS-33 and CC-OPS-34 did not exist in the first draft.** Capping
  delegations and tool calls is not enough — an agent can loop on the model many
  times between tool calls. The first run made **25 model requests and 38 tool
  calls** and then hung indefinitely on an unanswered request, because the HTTP
  client had no timeout. A limit that only bounds the things you thought of is
  not a budget.
- **A hard cap that raises is worse than one that degrades.** The first attempt
  used `UsageLimits(tool_calls_limit=...)`, which aborted the whole ticket with
  an exception and threw away all the work. Enforcing the same rule by removing
  tools from the agent's view produces the behaviour the rule actually wants:
  the agent stops gathering and answers from what it has.

### Known gaps

- ~~Agents can queue duplicate drafts.~~ **Fixed** — `prepare_customer_message`
  returns the existing draft for that ticket, counting both pending *and already
  approved* messages. Suppressing only pending ones was not enough: a ticket
  could never close, because each re-run queued a fresh draft that blocked it.
- ~~`approve_pending` is withheld from agents only by a backend toolset filter.~~
  **Hardened** — the server now refuses any agent name as `approved_by`, so the
  rule holds for every client rather than depending on one client's filter.
  Full per-client authorisation is still the right answer for a real deployment;
  MCP over stdio gives no identity to check.
- ~~A rejected approval does not annotate the originating ticket.~~ **Fixed** —
  rejecting an approval now writes the decision onto the ticket's notes, so a
  ticket cannot close as though the action had never been proposed.

### A real failure from the ticket 103 run, and what it taught

Run `7fadb10b069d` approved quoting Yale AI Club $46.40/unit for **20** hoodies
and **closed the ticket** — without ever calling `check_stock`. Only 8 are on
hand in size M. The audit trail shows the whole tool sequence, and `check_stock`
is not in it:

```
boss       list_open_tickets
boss       check_discount_margin
boss       ask_teammate -> accounting   (failed: Portkey 500)
accounting check_discount_margin  x2
boss       check_discount_margin
boss       close_ticket
```

Two causes, both worth fixing rather than excusing:

1. **The Boss prompt told it to check the money before promising, but never to
   check the stock before promising goods.** The rule existed for Inventory
   (CC-OPS-11) and the tool existed, but nothing required Boss to reach for it
   on a pricing ticket. A margin that works is not an order that can ship.
2. **When the delegation to Accounting failed with a Portkey 500, Boss treated
   the silence as sufficient** and proceeded on its own tool calls alone. A
   failed specialist should narrow confidence, not disappear.

Both are now addressed in `backend/prompts/boss.md`: step 3 requires a stock
check for any ticket naming a sku and qty, and the hard limits say a failed or
timed-out specialist must be named in the reasoning rather than silently absorbed.

This is the honest lesson of the problem: the guardrails that were enforced **in
code** (cash floor, no auto-pay, cycle refusal, close-blocked-while-pending) held
perfectly under every run. The one guardrail left to **prompt wording alone**
failed the first time a model got distracted by a vendor error. Anything that
actually matters belongs in the tool layer, not the prompt.


---

## 8. Owner's shop rules — reconciliation

Eight rules were supplied by the owner after the team was built. Four were
already enforced; four required changes.

| Owner rule | Status | Where |
|---|---|---|
| 1. `desk.date_today` is today | already enforced | `CC-OPS-21`, in code |
| 2. Lead times from `vendors` | already enforced | `CC-OPS-15`, `find_vendor_for_sku` |
| 3. **Vendor won't ship while owed** | **added** | `CC-OPS-35`, new tool + hard refusal |
| 4. Human approval for payments | already enforced | `CC-OPS-1`, agent toolsets filtered |
| 5. **Pay tool refuses, no negatives** | **added** | `CC-OPS-36`, absolute zero guard |
| 6. **Cash only goes out** | **added** | `CC-OPS-36`, `cash_is_outflow_only` + prompt bans |
| 7. **Reset before a full run** | **added** | `backend/reset_db.py` |
| 8. No emailing or calling | already enforced | `CC-OPS-16`, no send tool exists |

### What rule 3 does to this board

Bulldog Print Co is the shop's **only** apparel vendor and is owed $840 on the
overdue invoice #501. Both product tickets need apparel:

```
invoice #501 unpaid ($840, 3 days overdue)
   └─ Bulldog Print Co will not ship (CC-OPS-35)
        ├─ ticket 101  CC-TEE-WHITE size S, short 1   → cannot restock
        └─ ticket 103  CC-HOOD-NAVY size M, short 12  → cannot restock
```

And paying #501 after rent would leave $160, below the $500 floor. Under
CC-OPS-36 there is no way to raise the difference. **The entire board gates on
one human decision about a single $840 invoice** — which is a far better test of
a human-in-the-loop system than three independent tickets would have been.

The clean run confirmed the agents now reason this way. Boss on ticket 101:

> "Do not fulfill or promise a delivery date: size S is out of stock and Bulldog
> Print Co will not ship while invoice #501 remains unpaid. Keep the ticket open
> pending the human's cash decision."

Boss, Inventory **and** Accounting each independently called
`check_vendor_can_ship` in that run.

### Fixed defect: `close_ticket` guarded per-ticket, but work is cross-ticket

In the clean run, Accounting prepared the $2,400 rent payment **while working
ticket 101** (it was asked about the cash position there), so the approval was
tagged `ticket_id = 101`. When Boss later worked ticket 102 — the rent ticket —
it found no approval pending *against 102*, and closed it. Its note is honest
about what it did:

> "The same rent payment is already queued for human approval as approval #2
> under ticket 101; did not queue a duplicate. Ticket 102 has no approval pending
> against it."

The reasoning was defensible but the outcome was wrong: the rent ticket closed
while the rent was still unapproved.

**Fixed.** `close_ticket` now calls `_blocking_approvals()`, which matches a
pending action to a ticket by what it *refers to*, not only by the ticket it was
filed under: a rent payment whose `ref_id` is the ticket's `lease_id`, an invoice
payment matching its `invoice_id`, or a purchase order matching its `sku`/`size`.
Confirmed in the clean re-run — Boss said so itself:

> "I attempted to close the ticket, but closure was correctly refused because
> approval #2 is still pending and resolves this ticket too."

The general lesson: a guard keyed on how work was *filed* will miss work that was
done elsewhere. Key it on what the work *affects*.

### Fixed: timeouts that did not cancel

`CC-OPS-34` deadlines fire reliably at the delegation boundary — `delegation_timeout`
appears in the trail repeatedly. But twice a run has sat at 0% CPU for 15+ minutes
past its 600s ticket budget, so `asyncio.timeout` was not cancelling a call blocked
inside the HTTP client or the MCP stdio transport.

**Fixed.** Each ticket now runs in its own child process under a parent-held
660s hard kill (`run_ticket.py`). A deadline you can only enforce from inside the
thing you are timing is not a deadline. One wedged ticket no longer costs the
whole board — the parent kills it, reports it, and moves to the next ticket.

---

## 9. Final clean run

`python backend/run_ticket.py --all --reset` — database reset to original values
first, per shop rule 7. Three tickets, 152 audit entries, all `gpt-6-luna`.

| Ticket | Decision | Closed? |
|---|---|---|
| 101 | Stockout confirmed; Bulldog blocked by unpaid #501, so no delivery date promised. Customer draft queued. | no |
| 102 | Rent already queued under ticket 101; no duplicate filed. **Close refused** because that approval resolves this ticket too. | no |
| 103 | $46.40/unit approved (52.6% margin) but **fulfilment not promised** — 8 on hand against 20, restock blocked by #501. | no |

**Final board state:**

```
tickets     101 open, 102 open, 103 open
cash        $3,400.00   (unchanged)
payments    0
invoice 501 open
queued      #1 customer_message, #2 payment $2,400 — both awaiting a human
```

Three tickets worked end to end by five agents, and **not one cent moved**,
because only a human can move it. Every guardrail fired in this run: 4 cyclic
delegations refused (CC-OPS-27), 4 agent timeouts absorbed without taking the
run down (CC-OPS-34), Boss's tool budget exhausted on ticket 101 (CC-OPS-28).

Boss on ticket 103 drew the connection the whole board turns on:

> "Invoice #501 blocks restocks affecting tickets 101 and 103."

And on ticket 101, CC-OPS-36 showed up in the reasoning exactly as intended:

> "No money-inflow option is available."

All three tickets correctly remain **open**. Nothing can be resolved until a
person decides what to do about an $840 invoice — which is the right answer, and
the one the earlier buggy runs failed to reach.


---

## 10. Performance: diagnosing and fixing the timeouts

The first clean run lost 4 agents to timeouts. Measuring the audit trail rather
than guessing showed the cause was configuration, not the endpoint.

**Latency is bimodal.** A healthy model request returns in 5–15s; a wedged one
never returns. The slowest step measured **271.4s** — exactly `HTTP_TIMEOUT_S 90s
× 3 attempts`. A depth-1 specialist has a 300s budget, so **one wedged call
consumed 270s of it** and the agent died before it could answer. The timeouts
were self-inflicted by the retry setting.

**`CC-OPS-29` was declared but never implemented.** The rule said identical tool
calls should be cached within a run; nothing did. Every read tool was called
three times per ticket by three different agents:

```
list_open_tickets 3, get_cash_position 3, check_stock 3,
list_open_invoices 3, check_vendor_can_ship 3, find_vendor_for_sku 3
```

### Two fixes

1. **Fail fast, retry once.** `HTTP_TIMEOUT_S` 90s → 45s, `max_retries` 2 → 1.
   Worst case per call: 270s → 90s. Retrying a wedged call is near-worthless on
   this endpoint, so the trade costs almost nothing.
2. **`CachingToolset`** — a `WrapperToolset` holding a per-run cache keyed on
   `(tool_name, args)`, shared by all five agents. Write tools (`prepare_*`,
   `approve_*`, `close_*`) are **never** cached: queueing an approval twice must
   produce two approvals, not a reused result.

### Measured result, same three tickets, same clean board

| metric | before | after |
|---|---|---|
| wall clock | 970.6s | **556.6s** (−43%) |
| agent timeouts | 4 | **0** |
| slowest single step | 271.4s | **90.6s** |
| cache hits | 0 | **26** |
| model requests | 50 | 52 |
| audit entries | 152 | 186 |

Ticket 101 alone went from 303s to 96s — **3.1× faster**. Correctness was
unaffected: all three tickets still open, cash still $3,400, `payments` still
empty.

### A money bug the faster run exposed

With timeouts gone, Accounting got far enough to propose something it had never
reached before: a **$500 partial payment** toward the $840 invoice, which lands
the balance exactly on the $500 floor. That surfaced a real defect —
`approve_pending` marked an invoice `paid` on *any* approved amount, so
approving $500 would have settled an $840 debt.

Worse than an accounting error, it would have **silently unblocked the vendor**:
`check_vendor_can_ship` reads `invoices.status`, so the shop would have believed
it could reorder from Bulldog while $340 was still owed.

Fixed: an invoice is marked paid only when the **sum of all payments against it**
covers the amount. A partial payment is recorded, the invoice stays open, and the
vendor stays blocked. Verified on a scratch copy:

```
invoice_marked_paid: None
invoice_still_owed : 340.0
invoice 501 status : open
vendor can ship?   : False   <- correctly still blocked
```

The lesson worth keeping: **making the system faster made it reach decisions it
had never reached before, and those new paths had their own bugs.** Performance
work is not separable from correctness work — a slow system is also an
under-tested one.

---

## 11. The plan (Problem 6)

`output/desk_tickets.html` — standalone page, five tabs (101, 102, 103, Cash,
Reflection). Expected filled, Actual left empty for the comparison.

The governing constraint was restraint: **8 delegations across three tickets, and
no ticket uses all five agents.** Each ticket names the agent that should *not* be
called and why — that negative claim is the substance of the plan.

| Ticket | Boss calls first, and why | Delegations | Not called |
|---|---|---|---|
| 101 | **inventory** — "can we fill it" is a stock question; everything else is downstream of the answer | 3 | **facilities** — nothing touches the lease |
| 102 | **facilities** — lease ticket, and the ticket carries no dollar figure at all | 2 | **inventory** (no product), **customer_service** (no reply requested) |
| 103 | **accounting** — the question actually asked is about price | 3 | **facilities** — nothing touches the space |

Two edges are planned **specialist→specialist** rather than through Boss —
`inventory→accounting` on 101 and `facilities→accounting` on 102 — both where one
agent uncovers something squarely in another's domain. If every edge ran through
Boss the full-connectivity claim would be decoration.

**31 falsifiable checks** across three scorecards plus a board-level prediction,
so the comparison is mechanical rather than a judgement call. The sharpest is on
ticket 103: *"Ticket remains open — not closed on the strength of the price
alone."* An earlier run failed exactly that way, quoting $46.40 correctly while
12 units short, so the check has already caught something real once.

The page states openly that these tickets were run during Problem 5, so the plan
is informed rather than blind. Hiding that would make the plan look more
prescient than it is and the comparison less trustworthy.

---

## 12. Backend routes (Problem 7)

`backend/main.py` — FastAPI. Start it from the `backend/` folder:

```
uvicorn main:app --reload --port 8000
```

Docs at `http://localhost:8000/docs`. CORS is open to the Vite dev origins
(5173, 3000) so the React dashboard can call it.

| Route | What it does |
|---|---|
| `GET /` | What the API is, and an index of every route |
| `GET /health` | Liveness **plus a real MCP round trip**, so a green check means the whole chain works |
| `GET /tickets` | **(a)** Every ticket with `is_open` and a count of what is pending on it. `?status=all\|open\|resolved` |
| `GET /tickets/{id}` | One ticket in full |
| `POST /tickets/{id}/run` | **(b)** Run the agent team on one ticket. Returns a `run_id` in ~1s; does not block |
| `GET /runs` | Runs started by this server process, newest first |
| `GET /runs/{run_id}` | One run's status with a live count of what it has logged |
| `GET /events` | **(c)** Recent agent events — who acted, what they said, which tools they used. `?run_id=&ticket_id=&since=&limit=` |
| `GET /approvals` | What agents have queued for a human. `?status=pending\|approved\|rejected\|all` |
| `POST /approvals/{id}/decision` | **(d)** Approve or reject. **The only route that moves cash.** Records the person's name |
| `GET /cash` | **(f)** Checking balance plus every claim competing for it, the floor, and what the floor blocks |
| `POST /reset` | **(g)** Reset the database to original values. Refuses while a run is in flight; leaves the audit trail intact |

### Three decisions worth recording

**Everything goes through MCP.** Routes call the MCP server rather than opening
SQLite, so the dashboard, the agents and the vibe coder share one definition of
the shop and one place where rules are enforced. `/reset` is the sole exception —
it is a file operation on the database, not a fact about the shop.

**Running a ticket does not block.** A run is one to five minutes of live model
calls. `POST /tickets/{id}/run` spawns the same supervised worker the CLI uses,
hard-killed at 660s, and returns a `run_id` immediately — measured at **1s**. The
dashboard follows progress with `GET /events?run_id=…&since=…`, which returns
only what is new. A dashboard that hangs for four minutes on one request is not a
dashboard.

**A refusal is a 409, not a 500.** When the server declines to execute a payment
because it would breach the reserve floor, the request was well formed and the
shop's rules said no. That is the guardrail working, and the dashboard should
render it as an explanation rather than an error.

### Verified end to end against the live server

- `GET /health` → MCP connected, 3 tickets visible, shop date 2026-08-31
- `GET /cash` → $3,400, floor $500, obligations $3,240, `escalation_required: true`, invoice #501 listed as blocked by the floor
- `POST /approvals/{id}/decision` with a blank name → **400**, "must name a real person (CC-OPS-1)"
- Approving $2,400 rent → **200**, cash $3,400 → $1,000, `payments` row written with `approved_by: Kelly Enright`
- Approving a $500 partial on the $840 invoice → invoice **stays open**, `still_owed: 340.00`, vendor **stays blocked**
- Approving invoice #501 in full afterwards → **409**, "would leave $160.00, below the $500 reserve floor"; **cash unchanged**
- `POST /tickets/101/run` → `run_id` in **1s**; a second run on the same ticket → **409**; `POST /reset` while running → **409**
- `GET /events?since=` → incremental polling works; `tool_cache_hit` events are visible in the stream

### Duplicate drafts, fixed

The known duplicate-draft defect was closed here, since this is the problem where
the approval queue becomes something a person looks at. The API run left two
customer messages on ticket 101 — one from Customer Service, one from Boss after
Customer Service timed out. Both agents behaving sensibly; the queue reading badly.

`prepare_customer_message` now returns the existing pending draft for that ticket
instead of queueing a second, telling the agent which one exists and who wrote it,
and asking it to say so in its answer if its own draft differs materially. One
ticket, one pending draft.

### One bug this testing caught

After a partial payment, `check_vendor_can_ship` still reported the vendor was
owed the invoice's **face value** ($840) rather than what was outstanding ($340).
The shipping block was correct either way — an invoice only settles when paid in
full — but the figure shown to the person deciding was wrong, and it was the
figure telling them what it would cost to unblock the vendor. `_vendor_hold` now
subtracts payments made and reports `invoice_amount`, `paid_so_far` and the
remaining `amount` separately.

---

## 13. The dashboard (Problem 8)

`frontend/` — React 19 + Vite + TypeScript. Start it with `npm run dev`
(http://localhost:5173); it calls the backend at `http://localhost:8000`, which
allows that origin via CORS. Full rationale in `output/design.md`.

**Concept: the back office of HW 4's 1936 shop.** Same ink, paper and brass as
the storefront; different furniture, because this is a working room — desk
blotter and card stock instead of newsprint, mechanical motion instead of
editorial.

### Layout

Three columns, and the order is the argument: **in-tray → floor and wire →
your desk**. Work arrives on the left, happens in the middle, needs a signature
on the right. Collapses to one column below 1150px in the same order.

### What covers each requirement

| Asked for | Built |
|---|---|
| (a) list all three tickets | **In Tray** — docket cards with punch holes, stamped `OPEN`/`RESOLVED` |
| (b) pick one and start the team | Select a card, "Send the team in" → `POST /tickets/{id}/run` |
| (c) show each agent saying/doing | **The Floor** — five desks, each in its own hand, live status; **The Wire** — teletype of every event |
| (d) mark resolved when done | `RESOLVED` stamp presses on; board refreshes on `run_finished` |
| (e) short summary per agent | **The Docket** — one sentence per agent plus the guardrails that fired |
| (f) human approves pay/purchase | **Your Desk** — ledger paper for payments, carbon copies for letters, "Signing as" required |
| (g) show checking balance | **Cash Drawer** — counts down and flashes crimson when it falls |

### The three choices that carry the design

**Stationery, not colour-coding.** Each agent has its own typeface and paper —
Boss in Alfa Slab, Inventory in condensed stock-card numerals, Accounting in
tabular monospace on ledger green, Facilities in clerical lilac, Customer Service
in a typewriter face. Five coloured dots would satisfy "agents read differently"
literally and fail in practice; stationery makes a wall of events scannable
without a legend.

**The mesh drawn as ink threads.** Delegations appear as a line running from the
asker's colour to the answerer's, indented by depth. **A refused hand-off draws
as a broken red dash** rather than disappearing — when CC-OPS-27 refuses a cycle,
that is the system working and it belongs on screen. A list of events never shows
the topology; this does.

**Refusals are explanations, not errors.** A 409 from the approval route renders
in place as a stamped panel with the reason and the override, not a toast in
error red. The shop's rules declining a payment is the guardrail holding.

### Verified live

With the backend running and a real ticket-101 run in flight: tickets listed and
stamped; `● WORKING` on the running ticket; five desks showing live status with
real findings ("No. CC-TEE-WHITE size S has 0 units in Aisle B…"); the mesh
showing **5 hand-offs including two refused cycles in red dashes**; the wire
showing rule chips and amber `cached` entries; cash drawer showing $3,400 against
$3,240 of claims with invoice #501 flagged as blocked by the floor.

---

## 14. The full run (Problem 9)

Database reset to original values, then all three tickets worked until resolved.

**Starting checking balance: $3,400.00** · **Ending: $1,000.00** · reconciled against
`cash_accounts`, verified programmatically in `output/resolved_tickets.json`
(`cash_reconciliation.matches: true`).

| Ticket | Final status | Runs | Agents | Cash effect |
|---|---|---|---|---|
| 101 customer order | **resolved** | 2 | boss, inventory, accounting, facilities | $0.00 |
| 102 rent notice | **resolved** | 2 | boss, facilities, accounting | **−$2,400.00** |
| 103 discount request | **resolved** | 5 | all five | $0.00 |

```
starting                             $3,400.00
  101  order unfillable; no payment      $0.00
  102  rent paid (payment #1)        -$2,400.00
  103  quote issued; no payment          $0.00
                                    ───────────
ending (matches cash_accounts)       $1,000.00
```

**Only one payment moved**, and `payments.approved_by` holds a person's name.
Invoice #501 was deliberately left unpaid: rent ranks first under CC-OPS-3, and
paying both would leave $160 — below the $500 floor — with no inbound cash to
make it up (CC-OPS-36). So Bulldog Print Co stayed blocked and **neither product
ticket could be fulfilled, only decided and communicated.** All three still
resolved, because resolving a ticket means reaching and recording a decision.

### Plan versus reality

The plan in `output/desk_tickets.html` was mostly right, and wrong in one
interesting way.

**Held:** Boss's first call was correct on all three tickets (inventory → 101,
facilities → 102, accounting → 103). Ticket 102 ran exactly to plan — two
delegations, inventory and customer service never involved. `check_stock` was
called on 103, the check the plan most wanted. No delivery date was promised
anywhere, and no ticket closed on price alone.

**Missed:** Facilities was pulled into tickets 101 and 103, which the plan said
should not happen — Accounting wanted rent context before ranking the invoice
against it. Defensible, but one agent more than each ticket needed.

**The plan was wrong, not the team:** it predicted $46.40 for 20 hoodies at 52.6%
margin. Boss instead quoted the student-organisation rate on the **8 units
actually on hand**, reasoning a bulk tier should not apply to quantities it cannot
deliver. That is better commercial judgment than the plan had.

### Two defects this run exposed

**A self-reported close that never happened.** On one run Boss burned its 8-tool
budget (CC-OPS-28) re-checking pricing and vendors, so `close_ticket` was
withdrawn from its toolset before it could call it — and it then returned
`ticket_closed: true` anyway. The dashboard showed the ticket still open because
it reads `/tickets` from the database. **The structured output is the agent's
claim; the database is the truth**, and any display that trusts the former will
eventually lie.

**A ticket that could never close.** Every re-run of 103 queued a fresh customer
message, and that new pending item blocked `close_ticket` — so more work kept
arriving on a ticket that was trying to finish. Deduplication had only suppressed
*pending* duplicates; once a draft was approved the next run queued another.
`prepare_customer_message` now counts approved messages too. A guard that only
looks at in-flight work misses work that has already landed.

---

## 15. Index — what this system is

A complete map of the pieces, for anyone picking this up cold.

### Tables (§1) — `data/campus_customs_new.db`

`desk` (the shop's today) · `tickets` (the board) · `inventory` (stock per
sku+size) · `pricing` (cost and list) · `vendors` (specialty, lead days) ·
`leases` (rent, due dates) · `cash_accounts` (the one balance) · `invoices`
(what is owed) · `payments` (the audit trail of money, written only by a human's
approval) · `pending_approvals` (added in Problem 5 — the approval queue).

### MCP tools (§4, §6) — 14, in `mcp_server/`

**Read:** `list_open_tickets`, `check_stock`, `get_rent_obligation`,
`check_discount_margin`, `get_cash_position`, `list_open_invoices`,
`find_vendor_for_sku`, `check_vendor_can_ship`, `list_pending_approvals`.
**Prepare (never execute):** `prepare_payment`, `prepare_purchase_order`,
`prepare_customer_message`.
**Human only:** `approve_pending` (withheld from every agent), `close_ticket`.

### The five agents (§6) — `backend/`

**Boss** routes, arbitrates, and alone closes tickets · **Inventory** stock by
sku+size, shortfalls, restock routing · **Accounting** cash, invoices, margins,
payment preparation · **Facilities** leases, rent, the premises · **Customer
Service** drafts letters, never sends. Fully connected: every agent carries
`ask_teammate`, and specialist→specialist edges occurred in all three tickets.
One model throughout: `gpt-6-luna` via Portkey, named once in
`backend/agents/config.py`.

### API routes (§12) — `backend/main.py`, port 8000

`GET /tickets` · `POST /tickets/{id}/run` · `GET /events` · `GET /approvals` ·
`POST /approvals/{id}/decision` (the only route that moves cash) · `GET /cash` ·
`POST /reset` · plus `/health`, `/runs`, `/runs/{id}`.

### The dashboard (§13) — `frontend/`, port 5173

React 19 + Vite + TypeScript. A three-column desk: in-tray → floor and wire →
your desk. Each agent in its own stationery; delegations drawn as ink threads
with refusals as broken red dashes; a cash drawer that counts down and flashes
only when falling. Full rationale in `output/design.md`.

### Safety rules (§7) — 36 rules, `backend/prompts/shop_rules.md`

The ones that did real work in these runs:

| Rule | What it stopped |
|---|---|
| CC-OPS-1 | No agent moved money in any run. `approve_pending` is filtered out of every agent's toolset **and the server itself refuses any agent name as `approved_by`** |
| CC-OPS-2 | $500 floor refused the second payment at execution time — 409, cash unchanged |
| CC-OPS-27 | Refused cyclic delegations on every ticket |
| CC-OPS-28 | Withdrew tools from an agent that overspent its budget |
| CC-OPS-33/34 | Bounded model round-trips and killed wedged runs |
| CC-OPS-35 | Blocked restock from a vendor owed money — the constraint the whole board turned on |
| CC-OPS-36 | Kept the balance non-negative and kept "raise more cash" out of the agents' options |

The pattern worth keeping: **every guardrail enforced in code held in every run.
The ones left to prompt wording failed at least once.** Anything that actually
matters belongs in the tool layer.

### A late audit, and what it caught

Checking the finished system rather than trusting it found two holes worth
recording, because both are the same mistake in different clothes — **a rule
enforced in the wrong layer.**

**An agent could have named itself as the approver.** `approve_pending` rejected
a blank `approved_by` but accepted `"boss"`, and would have written a payment row
and debited cash. It had never mattered, because the backend filters the tool out
of every agent's toolset — but that is a *client-side* guarantee, and the MCP
server will answer anyone who connects to it, the vibe coder included. The server
now refuses every agent name itself:

```
approved_by='boss'             -> refused
approved_by='Accounting'       -> refused
approved_by='customer service'  -> refused
approved_by='AI'               -> refused
approved_by='Kelly Enright'    -> ACCEPTED
```

**A rejection left no trace.** Declining an approval updated the queue row and
nothing else, so a ticket could close looking as though the action had never been
proposed — a reader later cannot distinguish "never considered" from "considered
and refused". Rejecting now writes the decision onto the ticket's notes:

```
[2026-08-31] Kelly Enright REJECTED approval #7 (payment):
Pay $840.00 — invoice ref 501 (ticket 101) — not affordable this week
```

Both were in the "known gaps" list as things a real deployment would want. They
turned out to be cheap to close, and the first one was a genuine hole in the one
rule this assignment says loses points if broken.

