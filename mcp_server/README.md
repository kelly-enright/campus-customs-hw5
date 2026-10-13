# Campus Customs Operations MCP Server

## What it is for

The shared tool layer for the Campus Customs agent team. Boss, Inventory,
Accounting, Facilities, and Customer Service all call these tools instead of
querying SQLite themselves, so there is exactly one definition of what the shop
knows. When Accounting and Facilities both need the checking balance, they get
the same number from the same place.

Two rules are enforced in the tools so agents cannot drift from the data:

- **Nothing is invented.** Every value returned is a column from the database or
  arithmetic over columns. An unknown SKU, size, or lease comes back as
  `found: false` with the valid options listed — never a plausible-looking guess.
- **"Today" is `desk.date_today`**, not the system clock. The shop's clock reads
  `2026-08-31`; using the real date would make every due-date, overdue, and
  lead-time calculation wrong.

## Database

Reads `../data/campus_customs_new.db` — the **working copy**. The original
`data/campus_customs.db` is left untouched as a reference. The read tools open the file read-only. The prepare
and human tools write, but only ever through the approval queue — see below.

## The fourteen tools

Agents reach these through `load_mcp_toolsets(".mcp.json")` — the same config the
vibe coder uses, so there is one tools layer and no bypass.

### Read tools

| Tool | Tables | What it is for |
|---|---|---|
| `list_open_tickets(ticket_id=None)` | `tickets`, `desk` | The board. Entry point for every run; returns the shop's date alongside. |
| `check_stock(sku, size=None, qty_needed=None)` | `inventory` | On-hand units by `(sku, size)`, shortfall, and the restock quantity par implies. |
| `get_rent_obligation(lease_id)` | `leases`, `desk`, `cash_accounts` | Rent, days until due against the shop clock, and whether cash covers it. |
| `check_discount_margin(sku, qty, proposed_unit_price=None)` | `pricing` | Margin against real cost, the volume ladder, and both price floors. |
| `get_cash_position()` | `cash_accounts`, `invoices`, `leases`, `pending_approvals`, `desk` | Every claim on one balance, in priority order, with what the floor blocks. |
| `list_open_invoices(invoice_id=None)` | `invoices`, `vendors`, `desk` | Unpaid invoices with vendor and days overdue. |
| `find_vendor_for_sku(sku)` | `vendors`, `inventory`, `desk` | Ranks vendors by specialty match then lead time, showing its reasoning. |
| `check_vendor_can_ship(vendor_id)` | `vendors`, `invoices`, `desk` | Whether a vendor will accept an order, or is holding over an unpaid invoice (CC-OPS-35). |
| `list_pending_approvals(status='pending')` | `pending_approvals` | What is already queued for a human. |

### Prepare tools — queue an action, never execute it

| Tool | Writes | Notes |
|---|---|---|
| `prepare_payment(...)` | `pending_approvals` | Checks the $500 floor and records whether approval would breach it. Refuses any amount exceeding the balance (CC-OPS-36). |
| `prepare_purchase_order(...)` | `pending_approvals` | Costs the PO from `pricing.unit_cost`; the agent passes quantities, never prices. **Refuses outright** if the vendor is owed money (CC-OPS-35). |
| `prepare_customer_message(...)` | `pending_approvals` | Stores the draft against its ticket for human review. |

### Human tools

| Tool | Writes | Notes |
|---|---|---|
| `approve_pending(approval_id, approved_by, ...)` | `payments`, `cash_accounts`, `invoices`, `pending_approvals` | **The only tool that moves money.** Withheld from every agent; requires a named person; re-checks the cash floor at execution. |
| `close_ticket(ticket_id, resolution, closed_by)` | `tickets` | Refuses while any approval on that ticket is still pending. |

`pending_approvals` is created automatically on first write. It is the approval
queue: each row carries the action, the rule that sent it to a human, and who
prepared it.

## Running it

Not required yet; the agents wire up in a later problem. When you do need it:

```bash
cd mcp_server
../.venv/bin/python server.py          # stdio
../.venv/bin/python server.py --http   # http://127.0.0.1:8001/mcp
```

HTTP uses port 8001, leaving 8000 free for the FastAPI backend.

Dependencies: `fastmcp>=2.0.0` (see `requirements.txt`), installed in the
project-level `.venv` at the HW 5 root.
