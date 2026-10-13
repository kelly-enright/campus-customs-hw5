"""Campus Customs Operations MCP server.

Shared tool layer for the Campus Customs agent team (Boss, Inventory,
Accounting, Facilities, Customer Service). Every agent calls these tools rather
than reading the database directly, so there is one definition of "what the shop
knows" and one place where the shop's rules are enforced in code.

Reads and writes ../data/campus_customs_new.db. The original
../data/campus_customs.db is never touched.

Four rules are enforced here, not left to the model's goodwill:

1. Nothing is invented. Every value returned is a column or arithmetic over
   columns. A missing SKU, size, lease, or ticket comes back as ``found: false``
   with the valid options listed, never as a guess.
2. "Today" is ``desk.date_today``, not the system clock (CC-OPS-21).
3. No agent moves money (CC-OPS-1). The prepare_* tools only ever queue an
   action for a human; nothing debits cash or writes to ``payments`` except
   ``approve_pending``, which requires a named human approver.
4. The $500 cash reserve floor (CC-OPS-2) is checked when a payment is prepared
   AND re-checked when it is approved, because the balance can move in between.
5. A vendor holding an open unpaid invoice will not ship (CC-OPS-35). This is a
   hard refusal in prepare_purchase_order, not a warning, because an agent that
   can "note the risk and proceed" will eventually proceed.
6. The balance can never go negative, whatever the policy floor is set to
   (CC-OPS-36). Cash only leaves in this simulation; no revenue is modelled.

Run from this folder (stdio):  python mcp_server.py
Run (HTTP):                    python mcp_server.py --http
HTTP URL:                      http://127.0.0.1:8001/mcp
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"

# --- Policy constants (approved shop rules, see backend/prompts/shop_rules.md) ---
CASH_FLOOR = 500.0          # CC-OPS-2
PAR_LEVEL = 6               # CC-OPS-12
LOW_STOCK_AT = 3            # CC-OPS-12
HANDLING_DAYS = 1           # CC-OPS-15

# CC-OPS-14. SKU prefix -> product category, matched against vendors.specialty.
# This is a declared policy mapping, not a database fact: the schema has no
# SKU -> vendor key, and the product names share no words with the specialty
# strings ("Basic Hoodie" vs "apparel reprint"), so a text-overlap match would
# silently fail. Every vendor is returned regardless, with the basis shown, so
# the agent can see and override the ranking.
# CC-OPS-1. The approval tool is withheld from agents by the backend's toolset
# filter, but that is a client-side guarantee: anything else speaking to this
# server could still call it. The server therefore refuses to record any of these
# as the approving human, whoever is asking.
AGENT_NAMES = frozenset({
    "boss", "inventory", "accounting", "facilities", "customer_service",
    "agent", "system", "bot", "ai", "assistant", "campus-customs-ops",
})

SKU_CATEGORY = {
    "CC-TEE": "apparel",
    "CC-HOOD": "apparel",
    "CC-HAT": "apparel",
    "CC-MUG": "mugs",
}

mcp = FastMCP("campus-customs-ops")


# --------------------------------------------------------------------------
# database helpers
# --------------------------------------------------------------------------

def _read(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query against the working database."""
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _connect_rw() -> sqlite3.Connection:
    """Open the working database for writing, ensuring the approval queue exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_approvals (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            kind TEXT NOT NULL,
            summary TEXT NOT NULL,
            payload TEXT NOT NULL,
            amount REAL,
            rule_ids TEXT,
            reason TEXT,
            prepared_by TEXT NOT NULL,
            prepared_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            decided_by TEXT,
            decided_at TEXT,
            decision_note TEXT
        )
        """
    )
    conn.commit()
    return conn


def _shop_today() -> str:
    """The shop's current date, from the desk table — never the system clock."""
    rows = _read("SELECT date_today FROM desk LIMIT 1")
    return rows[0]["date_today"] if rows else ""


def _days_between(from_iso: str, to_iso: str) -> int | None:
    try:
        return (date.fromisoformat(to_iso) - date.fromisoformat(from_iso)).days
    except (ValueError, TypeError):
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _checking_balance(conn: sqlite3.Connection | None = None) -> float:
    sql = "SELECT COALESCE(SUM(balance), 0.0) AS b FROM cash_accounts"
    if conn is None:
        return _read(sql)[0]["b"]
    return conn.execute(sql).fetchone()["b"]


def _vendor_hold(vendor_id: int) -> list[dict]:
    """Open invoices for a vendor, with what is actually still outstanding.

    Reports the remaining balance, not the invoice face value: once a partial
    payment has been made, telling the human the vendor is owed the full amount
    overstates what it costs to unblock them. The invoice still blocks shipping
    either way (CC-OPS-35) — it is only settled when paid in full — but the
    number a person sees has to be the number they would actually pay.
    """
    today = _shop_today()
    rows = _read(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    )
    for r in rows:
        d = _days_between(today, r["due_date"])
        r["days_overdue"] = -d if (d is not None and d < 0) else 0
        r["is_overdue"] = d is not None and d < 0
        paid = _read(
            "SELECT COALESCE(SUM(amount), 0.0) AS s FROM payments "
            "WHERE kind = 'invoice' AND ref_id = ?", (r["id"],)
        )[0]["s"]
        r["invoice_amount"] = r["amount"]
        r["paid_so_far"] = round(paid, 2)
        r["amount"] = round(r["amount"] - paid, 2)  # what is still owed
    return rows


def _category_for_sku(sku: str) -> str | None:
    for prefix, category in SKU_CATEGORY.items():
        if sku.upper().startswith(prefix):
            return category
    return None


# --------------------------------------------------------------------------
# READ TOOLS
# --------------------------------------------------------------------------

@mcp.tool
def list_open_tickets(ticket_id: int | None = None, status: str = "open") -> dict:
    """List tickets on the board, or fetch one ticket in full.

    This is the agent team's entry point: Boss reads the board here before
    routing anything. Each ticket carries the foreign keys that say which other
    tables it reaches into (lease_id, invoice_id) and the product fields
    (sku, size, qty) a stock or pricing question needs.

    Pass ticket_id to get a single ticket regardless of its status. Pass
    status="all" for the whole board including resolved tickets — what a
    dashboard needs — or a specific status such as "resolved". The shop's
    current date is returned alongside, so every downstream date calculation
    anchors to the same day.
    """
    if ticket_id is not None:
        rows = _read("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if not rows:
            known = _read("SELECT id, status FROM tickets ORDER BY id")
            return {
                "found": False,
                "reason": f"No ticket with id {ticket_id}.",
                "known_tickets": known,
            }
        return {"found": True, "shop_today": _shop_today(), "tickets": rows}

    if status == "all":
        rows = _read("SELECT * FROM tickets ORDER BY id")
    else:
        rows = _read("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
    return {
        "found": True,
        "shop_today": _shop_today(),
        "status_filter": status,
        "count": len(rows),
        "open_count": sum(1 for r in rows if r["status"] == "open"),
        "tickets": rows,
    }


@mcp.tool
def check_stock(sku: str, size: str | None = None, qty_needed: int | None = None) -> dict:
    """Check on-hand units for a product, by SKU and size.

    Stock is tracked per (sku, size), so a SKU having units somewhere says
    nothing about the size a customer actually asked for. Always pass the size
    from the ticket when there is one.

    Pass qty_needed to get the shortfall computed against the requested size,
    plus the restock quantity implied by the par level (CC-OPS-13).

    Returns the requested size's quantity and location, a per-size breakdown of
    the whole SKU, and low-stock / stockout flags. If the SKU or size does not
    exist, returns found: false and lists what does exist, so no quantity is
    ever guessed.
    """
    rows = _read(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
        (sku,),
    )
    if not rows:
        known = _read("SELECT DISTINCT sku FROM inventory ORDER BY sku")
        return {
            "found": False,
            "reason": f"No SKU '{sku}' in the inventory table.",
            "known_skus": [r["sku"] for r in known],
        }

    result: dict = {
        "found": True,
        "sku": sku,
        "name": rows[0]["name"],
        "sizes": [
            {
                "size": r["size"],
                "qty": r["qty"],
                "location": r["location"],
                "stockout": r["qty"] == 0,
                "low_stock": 0 < r["qty"] <= LOW_STOCK_AT,
            }
            for r in rows
        ],
        "total_on_hand_all_sizes": sum(r["qty"] for r in rows),
        "par_level": PAR_LEVEL,
    }

    if size is None:
        return result

    match = next((r for r in rows if r["size"] == size), None)
    if match is None:
        return {
            **result,
            "found": False,
            "reason": f"SKU '{sku}' exists but is not stocked in size '{size}'.",
            "available_sizes": [r["size"] for r in rows],
        }

    result["requested_size"] = size
    result["qty_on_hand"] = match["qty"]
    result["location"] = match["location"]
    result["in_stock"] = match["qty"] > 0
    result["stockout"] = match["qty"] == 0
    result["low_stock"] = 0 < match["qty"] <= LOW_STOCK_AT

    if qty_needed is not None:
        shortfall = max(0, qty_needed - match["qty"])
        result["qty_needed"] = qty_needed
        result["shortfall"] = shortfall
        result["can_fulfill_from_stock"] = shortfall == 0
        # CC-OPS-13: cover the shortfall, then top the size back up to par.
        result["restock_qty_per_cc_ops_13"] = (
            shortfall + max(0, PAR_LEVEL - max(0, match["qty"] - qty_needed))
            if shortfall
            else 0
        )

    return result


@mcp.tool
def get_rent_obligation(lease_id: int) -> dict:
    """Look up a lease's rent, its due date relative to the shop's today, and whether cash covers it.

    Answers the three things that have to be settled together before rent can be
    scheduled: how much is owed, how long until it is late, and whether the money
    is actually in the account. Reporting the amount without the balance invites
    approving a payment the shop cannot make.

    days_until_due is measured from desk.date_today, so a negative value means
    the rent is already late. The $500 reserve floor (CC-OPS-2) is applied to the
    post-payment balance. Returns found: false for an unknown lease_id.
    """
    leases = _read(
        "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
        (lease_id,),
    )
    if not leases:
        known = _read("SELECT id, space_name FROM leases ORDER BY id")
        return {"found": False, "reason": f"No lease with id {lease_id}.", "known_leases": known}

    lease = leases[0]
    today = _shop_today()
    days = _days_between(today, lease["next_due"])
    accounts = _read("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    total_cash = sum(a["balance"] for a in accounts)
    rent = lease["monthly_rent"]
    after = total_cash - rent

    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "shop_today": today,
        "days_until_due": days,
        "is_overdue": days is not None and days < 0,
        "notes": lease["notes"],
        "cash_accounts": accounts,
        "total_cash": round(total_cash, 2),
        "cash_covers_rent": total_cash >= rent,
        "cash_after_paying_rent": round(after, 2),
        "cash_floor": CASH_FLOOR,
        "respects_cash_floor": after >= CASH_FLOOR,
    }


@mcp.tool
def check_discount_margin(sku: str, qty: int, proposed_unit_price: float | None = None) -> dict:
    """Price a bulk or discount request against the SKU's real cost, and report the margin.

    A discount request cannot be answered from the list price alone — what
    matters is the gap between the proposed price and unit_cost. This returns
    the baseline economics at list, the discount the volume ladder (CC-OPS-6)
    allows for this quantity, and — when a price is proposed — the margin and
    total profit at that price plus whether it clears the 40% margin floor
    (CC-OPS-8) and the absolute cost floor (CC-OPS-9).

    break_even_unit_price is the SKU's unit_cost. Returns found: false for an
    unpriced SKU.
    """
    rows = _read("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if not rows:
        known = _read("SELECT sku FROM pricing ORDER BY sku")
        return {
            "found": False,
            "reason": f"No pricing row for SKU '{sku}'.",
            "priced_skus": [r["sku"] for r in known],
        }

    unit_cost = rows[0]["unit_cost"]
    list_price = rows[0]["list_price"]

    # CC-OPS-6 volume ladder.
    if qty >= 50:
        ladder = 20
    elif qty >= 20:
        ladder = 15
    elif qty >= 10:
        ladder = 10
    else:
        ladder = 0

    result: dict = {
        "found": True,
        "sku": sku,
        "qty": qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "break_even_unit_price": unit_cost,
        "margin_floor_pct": 40.0,
        "ladder_discount_pct_cc_ops_6": ladder,
        "ladder_unit_price": round(list_price * (1 - ladder / 100), 2),
        "student_org_extra_pct_cc_ops_7": 5,
        "max_unit_price_with_student_org": round(list_price * (1 - (ladder + 5) / 100), 2),
        "at_list": {
            "unit_price": list_price,
            "revenue": round(qty * list_price, 2),
            "cost_of_goods": round(qty * unit_cost, 2),
            "gross_profit": round(qty * (list_price - unit_cost), 2),
            "margin_pct": round(100.0 * (list_price - unit_cost) / list_price, 1)
            if list_price
            else None,
        },
    }

    if proposed_unit_price is None:
        return result

    margin_pct = (
        round(100.0 * (proposed_unit_price - unit_cost) / proposed_unit_price, 1)
        if proposed_unit_price
        else None
    )
    result["proposed"] = {
        "unit_price": proposed_unit_price,
        "discount_off_list_pct": round(100.0 * (list_price - proposed_unit_price) / list_price, 1)
        if list_price
        else None,
        "revenue": round(qty * proposed_unit_price, 2),
        "cost_of_goods": round(qty * unit_cost, 2),
        "gross_profit": round(qty * (proposed_unit_price - unit_cost), 2),
        "margin_pct": margin_pct,
        "above_cost": proposed_unit_price > unit_cost,
        "clears_margin_floor_cc_ops_8": margin_pct is not None and margin_pct >= 40.0,
        "within_ladder_cc_ops_6": proposed_unit_price >= round(list_price * (1 - (ladder + 5) / 100), 2) - 0.005,
        "gross_profit_given_up_vs_list": round(qty * (list_price - proposed_unit_price), 2),
    }
    return result


@mcp.tool
def get_cash_position() -> dict:
    """Total cash against every claim on it: open invoices, rent due, and already-queued payments.

    The single most important tool for cross-ticket decisions. Each ticket looked
    at alone appears affordable; this is the only view that shows the claims
    competing for one balance, so it is what stops an agent approving a payment
    the shop cannot actually make once the other tickets land.

    Applies the $500 reserve floor (CC-OPS-2) and reports, in the priority order
    of CC-OPS-3, how far down the obligation list the shop can actually fund.
    """
    today = _shop_today()
    accounts = _read("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    cash = sum(a["balance"] for a in accounts)

    invoices = _read(
        """
        SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date,
               i.status, i.description
        FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
        WHERE i.status = 'open' ORDER BY i.due_date
        """
    )
    for inv in invoices:
        d = _days_between(today, inv["due_date"])
        inv["days_until_due"] = d
        inv["is_overdue"] = d is not None and d < 0

    leases = _read("SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY id")
    for ls in leases:
        d = _days_between(today, ls["next_due"])
        ls["days_until_due"] = d
        ls["is_overdue"] = d is not None and d < 0

    queued = _read(
        "SELECT id, ticket_id, kind, summary, amount FROM pending_approvals "
        "WHERE status = 'pending' AND amount IS NOT NULL ORDER BY id"
    ) if _table_exists("pending_approvals") else []

    # CC-OPS-3 priority: rent first, then overdue payables oldest first, then the rest.
    obligations = [
        {"priority": 1, "kind": "rent", "ref_id": ls["id"], "label": f"Rent — {ls['space_name']}",
         "amount": ls["monthly_rent"], "due": ls["next_due"], "is_overdue": ls["is_overdue"]}
        for ls in leases
    ]
    overdue = [i for i in invoices if i["is_overdue"]]
    not_yet = [i for i in invoices if not i["is_overdue"]]
    obligations += [
        {"priority": 2, "kind": "invoice", "ref_id": i["id"],
         "label": f"Invoice #{i['id']} — {i['vendor_name']}", "amount": i["amount"],
         "due": i["due_date"], "is_overdue": True}
        for i in sorted(overdue, key=lambda x: x["due_date"])
    ]
    obligations += [
        {"priority": 3, "kind": "invoice", "ref_id": i["id"],
         "label": f"Invoice #{i['id']} — {i['vendor_name']}", "amount": i["amount"],
         "due": i["due_date"], "is_overdue": False}
        for i in sorted(not_yet, key=lambda x: x["due_date"])
    ]

    running = cash
    fundable, blocked = [], []
    for ob in obligations:
        if running - ob["amount"] >= CASH_FLOOR:
            running -= ob["amount"]
            ob["balance_after"] = round(running, 2)
            fundable.append(ob)
        else:
            ob["balance_after_if_paid"] = round(running - ob["amount"], 2)
            ob["blocked_by"] = f"would breach the ${CASH_FLOOR:.0f} reserve floor (CC-OPS-2)"
            blocked.append(ob)

    total_ob = sum(o["amount"] for o in obligations)
    return {
        "found": True,
        "shop_today": today,
        "cash_accounts": accounts,
        "total_cash": round(cash, 2),
        # CC-OPS-36. No revenue is modelled, so the balance only ever falls.
        # Any plan that depends on money arriving is not a plan.
        "cash_is_outflow_only_cc_ops_36": True,
        "no_inbound_cash_note": "Revenue is not modelled in this shop. The balance "
                                "can only decrease, so 'raise more cash' is never an "
                                "available option — do not offer it.",
        "cash_floor_cc_ops_2": CASH_FLOOR,
        "spendable_above_floor": round(cash - CASH_FLOOR, 2),
        "open_invoices": invoices,
        "leases": leases,
        "already_queued_for_approval": queued,
        "obligations_in_priority_order_cc_ops_3": obligations,
        "total_obligations": round(total_ob, 2),
        "cash_minus_obligations": round(cash - total_ob, 2),
        "can_fund_everything": (cash - total_ob) >= CASH_FLOOR,
        "fundable_within_floor": fundable,
        "blocked_by_floor": blocked,
        "escalation_required_cc_ops_4": bool(blocked),
    }


def _table_exists(name: str) -> bool:
    return bool(_read("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))


@mcp.tool
def list_open_invoices(invoice_id: int | None = None) -> dict:
    """List unpaid vendor invoices with their vendor and overdue status, or fetch one invoice.

    Ticket 101 carries invoice_id 501, so this is how the customer order connects
    to what the shop owes: the reprint that would end the stockout is already
    invoiced and unpaid. Overdue status is measured against desk.date_today.
    """
    today = _shop_today()
    if invoice_id is not None:
        rows = _read(
            """
            SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty,
                   v.lead_days AS vendor_lead_days
            FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?
            """,
            (invoice_id,),
        )
        if not rows:
            known = _read("SELECT id, status FROM invoices ORDER BY id")
            return {"found": False, "reason": f"No invoice {invoice_id}.", "known_invoices": known}
    else:
        rows = _read(
            """
            SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty,
                   v.lead_days AS vendor_lead_days
            FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
            WHERE i.status = 'open' ORDER BY i.due_date
            """
        )
    for r in rows:
        d = _days_between(today, r["due_date"])
        r["days_until_due"] = d
        r["is_overdue"] = d is not None and d < 0
        r["days_overdue"] = -d if (d is not None and d < 0) else 0
    return {"found": True, "shop_today": today, "count": len(rows), "invoices": rows}


@mcp.tool
def find_vendor_for_sku(sku: str) -> dict:
    """Rank vendors able to restock a SKU, by specialty match then lead time (CC-OPS-14).

    The schema has no SKU-to-vendor key, so this applies the declared policy
    mapping from SKU prefix to product category and matches that against
    vendors.specialty. Every vendor is returned with its match basis and lead
    time, so the ranking is visible and an agent can override it with a reason
    rather than being handed a single opaque answer.

    earliest_delivery_day adds the one day of handling required by CC-OPS-15.
    """
    product = _read("SELECT DISTINCT sku, name FROM inventory WHERE sku = ?", (sku,))
    if not product:
        known = _read("SELECT DISTINCT sku FROM inventory ORDER BY sku")
        return {
            "found": False,
            "reason": f"No SKU '{sku}' in the inventory table.",
            "known_skus": [r["sku"] for r in known],
        }

    category = _category_for_sku(sku)
    today = _shop_today()
    vendors = _read("SELECT id, name, specialty, lead_days FROM vendors ORDER BY lead_days")
    ranked = []
    for v in vendors:
        matches = category is not None and category in v["specialty"].lower()
        eta_days = v["lead_days"] + HANDLING_DAYS
        eta = None
        try:
            eta = (date.fromisoformat(today) + __import__("datetime").timedelta(days=eta_days)).isoformat()
        except (ValueError, TypeError):
            pass
        hold = _vendor_hold(v["id"])
        ranked.append({
            **v,
            "can_ship_cc_ops_35": not hold,
            "blocking_unpaid_invoices": hold,
            "blocked_reason": (
                f"{v['name']} holds {len(hold)} unpaid invoice(s) totalling "
                f"${sum(h['amount'] for h in hold):,.2f}; they will not ship until paid."
            ) if hold else None,
            "specialty_matches_category": matches,
            "match_basis": f"sku prefix -> category '{category}' vs specialty '{v['specialty']}'"
            if category
            else "no category mapping for this SKU prefix",
            "lead_days_plus_handling_cc_ops_15": eta_days,
            "earliest_delivery_day": eta,
        })
    # A blocked vendor sorts last however good its specialty match is: a vendor
    # that will not ship is not a restock option, it is a payment problem.
    ranked.sort(key=lambda v: (not v["can_ship_cc_ops_35"],
                               not v["specialty_matches_category"], v["lead_days"]))
    matched = [v for v in ranked if v["specialty_matches_category"]]
    shippable = [v for v in matched if v["can_ship_cc_ops_35"]]
    recommended = shippable[0] if shippable else None
    blocked_match = matched[0] if matched and not shippable else None

    note = None
    if blocked_match:
        total = sum(h["amount"] for h in blocked_match["blocking_unpaid_invoices"])
        ids = ", ".join(f"#{h['id']}" for h in blocked_match["blocking_unpaid_invoices"])
        note = (
            f"No restock is possible for {sku} right now. The only vendor matching "
            f"'{category}' is {blocked_match['name']}, and they will not ship while "
            f"invoice(s) {ids} totalling ${total:,.2f} are unpaid (CC-OPS-35). "
            f"Paying that invoice is the unblocking step — treat it as a cash "
            f"decision for a human, not a sourcing decision."
        )
    elif recommended is None:
        note = "No vendor matched the product category; choose explicitly and say why."

    return {
        "found": True,
        "sku": sku,
        "product_name": product[0]["name"],
        "product_category": category,
        "shop_today": today,
        "vendors_ranked": ranked,
        "recommended_vendor": recommended,
        "restock_blocked_cc_ops_35": bool(blocked_match),
        "blocked_vendor": blocked_match,
        "note": note,
    }


@mcp.tool
def check_vendor_can_ship(vendor_id: int) -> dict:
    """Check whether a vendor will accept a new order, or is holding over an unpaid invoice.

    A vendor with an open unpaid invoice will not ship new product (CC-OPS-35).
    Call this before planning any restock: a lead time is meaningless if the
    vendor is refusing orders, and the fix is a payment decision rather than a
    sourcing one.

    Returns the vendor, whether they can ship, and — when they cannot — every
    invoice blocking them and the amount that would unblock them.
    """
    rows = _read("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if not rows:
        known = _read("SELECT id, name, specialty FROM vendors ORDER BY id")
        return {"found": False, "reason": f"No vendor {vendor_id}.", "known_vendors": known}

    v = rows[0]
    hold = _vendor_hold(vendor_id)
    total_owed = round(sum(h["amount"] for h in hold), 2)
    today = _shop_today()
    eta = None
    if not hold:
        try:
            from datetime import timedelta
            eta = (date.fromisoformat(today)
                   + timedelta(days=v["lead_days"] + HANDLING_DAYS)).isoformat()
        except (ValueError, TypeError):
            pass

    return {
        "found": True,
        "vendor": v,
        "shop_today": today,
        "can_ship": not hold,
        "blocking_unpaid_invoices": hold,
        "total_owed": total_owed,
        "earliest_delivery_day_if_unblocked": eta,
        "reason": None if not hold else
                  f"{v['name']} holds {len(hold)} unpaid invoice(s) totalling "
                  f"${total_owed:,.2f} and will not ship until paid (CC-OPS-35).",
        "unblocking_step": None if not hold else
                           f"Pay ${total_owed:,.2f} to {v['name']}; that is a human "
                           f"approval decision, not something an agent can do.",
        "rules_applied": ["CC-OPS-35"],
    }


@mcp.tool
def list_pending_approvals(status: str = "pending") -> dict:
    """List actions agents have queued for a human to decide (CC-OPS-1).

    Everything an agent prepares — payments, purchase orders, customer messages —
    waits here. Agents read this to avoid queueing the same action twice and to
    see what is already committed against the cash balance.
    """
    if not _table_exists("pending_approvals"):
        return {"found": True, "count": 0, "approvals": []}
    rows = _read(
        "SELECT * FROM pending_approvals WHERE status = ? ORDER BY id"
        if status != "all"
        else "SELECT * FROM pending_approvals ORDER BY id",
        () if status == "all" else (status,),
    )
    for r in rows:
        try:
            r["payload"] = json.loads(r["payload"])
        except (ValueError, TypeError):
            pass
    return {"found": True, "count": len(rows), "status_filter": status, "approvals": rows}


# --------------------------------------------------------------------------
# PREPARE TOOLS — queue an action for a human. These never move money.
# --------------------------------------------------------------------------

def _queue(ticket_id, kind, summary, payload, amount, rule_ids, reason, prepared_by) -> dict:
    conn = _connect_rw()
    try:
        cur = conn.execute(
            """
            INSERT INTO pending_approvals
                (ticket_id, kind, summary, payload, amount, rule_ids, reason,
                 prepared_by, prepared_at, status)
            VALUES (?,?,?,?,?,?,?,?,?,'pending')
            """,
            (ticket_id, kind, summary, json.dumps(payload), amount,
             ",".join(rule_ids), reason, prepared_by, _now()),
        )
        conn.commit()
        return {"approval_id": cur.lastrowid}
    finally:
        conn.close()


@mcp.tool
def prepare_payment(
    ticket_id: int,
    kind: str,
    ref_id: int,
    amount: float,
    reason: str,
    prepared_by: str,
    account: str = "checking",
) -> dict:
    """Queue a payment for human approval. Does NOT pay anything (CC-OPS-1).

    Use kind='rent' with the lease id, or kind='invoice' with the invoice id.
    The $500 reserve floor (CC-OPS-2) is checked here and the result is recorded
    on the queued item, so the human sees whether approving it would breach the
    floor before they decide.

    Returns the approval_id and the projected balance. An agent must never write
    to the payments table directly and must never name itself as approver.
    """
    if kind not in ("rent", "invoice"):
        return {"ok": False, "reason": "kind must be 'rent' or 'invoice'."}
    if amount <= 0:
        return {"ok": False, "reason": "amount must be positive."}

    if kind == "invoice":
        target = _read("SELECT id, amount, status FROM invoices WHERE id = ?", (ref_id,))
        if not target:
            return {"ok": False, "reason": f"No invoice {ref_id}."}
        if target[0]["status"] != "open":
            return {"ok": False, "reason": f"Invoice {ref_id} is already '{target[0]['status']}'."}
    else:
        target = _read("SELECT id, monthly_rent FROM leases WHERE id = ?", (ref_id,))
        if not target:
            return {"ok": False, "reason": f"No lease {ref_id}."}

    cash = _checking_balance()
    if amount > cash:
        return {
            "ok": False,
            "reason": f"Refused: ${amount:,.2f} exceeds the ${cash:,.2f} on hand. "
                      f"The balance may never go negative (CC-OPS-36).",
            "cash_now": round(cash, 2),
            "shortfall": round(amount - cash, 2),
        }
    committed = _read(
        "SELECT COALESCE(SUM(amount),0.0) AS s FROM pending_approvals "
        "WHERE status='pending' AND amount IS NOT NULL"
    )[0]["s"] if _table_exists("pending_approvals") else 0.0
    after = cash - committed - amount
    breaches = after < CASH_FLOOR

    rules = ["CC-OPS-1", "CC-OPS-2"]
    if breaches:
        rules.append("CC-OPS-4")

    summary = f"Pay ${amount:,.2f} — {kind} ref {ref_id} (ticket {ticket_id})"
    queued = _queue(ticket_id, "payment", summary,
                    {"kind": kind, "ref_id": ref_id, "amount": amount, "account": account},
                    amount, rules, reason, prepared_by)

    return {
        "ok": True,
        **queued,
        "status": "pending_human_approval",
        "summary": summary,
        "cash_now": round(cash, 2),
        "already_committed_to_other_pending": round(committed, 2),
        "projected_balance_if_approved": round(after, 2),
        "cash_floor": CASH_FLOOR,
        "breaches_cash_floor_cc_ops_2": breaches,
        "escalation_note": "Approving this would drop the shop below its reserve floor; "
                           "CC-OPS-4 requires the conflict be surfaced with options."
        if breaches else None,
        "rules_applied": rules,
    }


@mcp.tool
def prepare_purchase_order(
    ticket_id: int,
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    reason: str,
    prepared_by: str,
) -> dict:
    """Queue a restock purchase order for human approval. Does NOT order anything.

    Cost is taken from pricing.unit_cost — the agent does not supply a price, so
    a PO total can never be invented. The vendor's lead time plus one handling
    day (CC-OPS-15) gives the earliest delivery date the shop may promise.
    """
    if qty <= 0:
        return {"ok": False, "reason": "qty must be positive."}
    vendor = _read("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,))
    if not vendor:
        known = _read("SELECT id, name, specialty FROM vendors ORDER BY id")
        return {"ok": False, "reason": f"No vendor {vendor_id}.", "known_vendors": known}
    price = _read("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,))
    if not price:
        return {"ok": False, "reason": f"No pricing row for SKU '{sku}'; cannot cost this PO."}
    stock = _read("SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    if not stock:
        return {"ok": False, "reason": f"SKU '{sku}' is not stocked in size '{size}'."}

    v = vendor[0]
    # CC-OPS-35: a vendor with an open unpaid invoice will not ship. Refuse the
    # PO outright rather than queueing something the vendor would reject.
    hold = _vendor_hold(vendor_id)
    if hold:
        total_owed = sum(h["amount"] for h in hold)
        return {
            "ok": False,
            "reason": f"{v['name']} will not ship while invoice(s) "
                      f"{', '.join('#' + str(h['id']) for h in hold)} totalling "
                      f"${total_owed:,.2f} are unpaid (CC-OPS-35).",
            "vendor": v,
            "blocking_unpaid_invoices": hold,
            "unblocking_step": f"Pay ${total_owed:,.2f} to {v['name']}. That is a "
                               f"human approval decision — queue it with prepare_payment "
                               f"and surface the cash conflict if it breaches the floor.",
            "rules_applied": ["CC-OPS-35"],
        }
    unit_cost = price[0]["unit_cost"]
    total = round(qty * unit_cost, 2)
    today = _shop_today()
    eta_days = v["lead_days"] + HANDLING_DAYS
    try:
        from datetime import timedelta
        eta = (date.fromisoformat(today) + timedelta(days=eta_days)).isoformat()
    except (ValueError, TypeError):
        eta = None

    category = _category_for_sku(sku)
    mismatch = category is not None and category not in v["specialty"].lower()

    summary = f"PO {qty} x {sku} ({size}) from {v['name']} — ${total:,.2f} (ticket {ticket_id})"
    rules = ["CC-OPS-1", "CC-OPS-13", "CC-OPS-14", "CC-OPS-15"]
    queued = _queue(ticket_id, "purchase_order", summary,
                    {"vendor_id": vendor_id, "vendor_name": v["name"], "sku": sku, "size": size,
                     "qty": qty, "unit_cost": unit_cost, "total_cost": total,
                     "earliest_delivery_day": eta},
                    total, rules, reason, prepared_by)

    return {
        "ok": True,
        **queued,
        "status": "pending_human_approval",
        "summary": summary,
        "vendor": v,
        "unit_cost_from_pricing": unit_cost,
        "total_cost": total,
        "qty_on_hand_now": stock[0]["qty"],
        "earliest_delivery_day_cc_ops_15": eta,
        "specialty_mismatch_cc_ops_14": mismatch,
        "warning": f"{v['name']} specialises in '{v['specialty']}' but {sku} is '{category}'."
        if mismatch else None,
        "rules_applied": rules,
    }


@mcp.tool
def prepare_customer_message(
    ticket_id: int, to: str, subject: str, body: str, prepared_by: str
) -> dict:
    """Queue a drafted customer message for a human to review and send (CC-OPS-16).

    No agent contacts a customer directly. The draft is stored against the ticket
    so the human sees the message and the ticket together before anything is sent.
    """
    if not body.strip():
        return {"ok": False, "reason": "body is empty."}
    ticket = _read("SELECT id, requester FROM tickets WHERE id = ?", (ticket_id,))
    if not ticket:
        return {"ok": False, "reason": f"No ticket {ticket_id}."}

    # One ticket, one customer message — counting messages already APPROVED, not
    # just pending ones. Suppressing only pending duplicates is not enough: once a
    # draft is approved, the next run of the same ticket queues a fresh one, that
    # new pending item blocks close_ticket, and the ticket can never be closed. A
    # ticket that already has a letter out does not need another to be resolved.
    if _table_exists("pending_approvals"):
        existing = _read(
            "SELECT id, summary, prepared_by, prepared_at, status FROM pending_approvals "
            "WHERE ticket_id = ? AND kind = 'customer_message' "
            "AND status IN ('pending','approved') ORDER BY id LIMIT 1",
            (ticket_id,),
        )
        if existing:
            e = existing[0]
            return {
                "ok": True,
                "approval_id": e["id"],
                "status": "pending_human_approval",
                "deduplicated": True,
                "summary": e["summary"],
                "already_status": e["status"],
                "reason": f"Ticket {ticket_id} already has a customer message "
                          f"({'awaiting approval' if e['status'] == 'pending' else 'approved and sent'}) "
                          f"— #{e['id']}, drafted by {e['prepared_by']}. Returning that one rather "
                          f"than queueing another for the same ticket.",
                "guidance": "The customer has been written to. Do not queue another draft; if "
                            "your wording differs materially, say so in your answer instead. "
                            "If nothing else is pending, this ticket can be closed.",
                "rules_applied": ["CC-OPS-16"],
            }

    summary = f"Message to {to} re ticket {ticket_id}: {subject}"
    queued = _queue(ticket_id, "customer_message", summary,
                    {"to": to, "subject": subject, "body": body},
                    None, ["CC-OPS-16", "CC-OPS-17", "CC-OPS-18"], "customer communication",
                    prepared_by)
    return {
        "ok": True,
        **queued,
        "status": "pending_human_approval",
        "summary": summary,
        "ticket_requester": ticket[0]["requester"],
        "rules_applied": ["CC-OPS-16", "CC-OPS-17", "CC-OPS-18"],
    }


# --------------------------------------------------------------------------
# HUMAN TOOLS — not exposed to agents. The dashboard calls these.
# --------------------------------------------------------------------------

@mcp.tool
def approve_pending(approval_id: int, approved_by: str, decision: str = "approve",
                    note: str | None = None) -> dict:
    """HUMAN ONLY. Approve or reject a queued action and execute it (CC-OPS-1).

    This is the only tool that moves money. It is deliberately withheld from the
    agent team and called by the dashboard on a person's behalf; approved_by must
    be a real person's name. The cash floor (CC-OPS-2) is re-checked here because
    the balance may have moved since the action was queued.

    On approval: a payment writes a payments row, debits the account, and marks
    an invoice paid. A purchase order and a customer message are recorded as
    approved; neither moves stock, because goods are not received at approval
    time and the message is sent by the human.
    """
    if decision not in ("approve", "reject"):
        return {"ok": False, "reason": "decision must be 'approve' or 'reject'."}
    approver = approved_by.strip()
    if not approver:
        return {"ok": False, "reason": "approved_by must name a real person (CC-OPS-1)."}
    # An agent must never appear as the approver of a money movement. Enforced
    # here rather than only in the backend, so the rule holds for every client.
    normalised = approver.lower().replace(" ", "_").replace("-", "_")
    if normalised in AGENT_NAMES or any(normalised == a for a in AGENT_NAMES):
        return {
            "ok": False,
            "reason": f"'{approver}' is an agent, not a person. Only a named human may "
                      f"approve an action that moves money or reaches a customer (CC-OPS-1).",
            "rules_applied": ["CC-OPS-1"],
        }
    approved_by = approver

    conn = _connect_rw()
    try:
        row = conn.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return {"ok": False, "reason": f"No pending approval {approval_id}."}
        if row["status"] != "pending":
            return {"ok": False, "reason": f"Approval {approval_id} is already '{row['status']}'."}

        payload = json.loads(row["payload"])

        if decision == "reject":
            conn.execute(
                "UPDATE pending_approvals SET status='rejected', decided_by=?, decided_at=?, "
                "decision_note=? WHERE id=?",
                (approved_by, _now(), note, approval_id),
            )
            # Write the rejection onto the ticket too. A declined action that
            # leaves no mark lets a ticket close as though nothing was ever
            # proposed — the person reading it later cannot tell the difference
            # between "never considered" and "considered and refused".
            annotated = False
            if row["ticket_id"] is not None:
                tk = conn.execute(
                    "SELECT id, notes FROM tickets WHERE id = ?", (row["ticket_id"],)
                ).fetchone()
                if tk is not None:
                    line = (f"[{_shop_today()}] {approved_by} REJECTED approval #{approval_id} "
                            f"({row['kind']}): {row['summary']}"
                            + (f" — {note}" if note else ""))
                    conn.execute(
                        "UPDATE tickets SET notes = ? WHERE id = ?",
                        (f"{tk['notes'] or ''}\n{line}".strip(), row["ticket_id"]),
                    )
                    annotated = True
            conn.commit()
            return {"ok": True, "approval_id": approval_id, "status": "rejected",
                    "decided_by": approved_by, "ticket_id": row["ticket_id"],
                    "ticket_annotated": annotated,
                    "note": "Rejection recorded on the ticket so it is visible later."
                            if annotated else None}

        executed: dict = {}
        if row["kind"] == "payment":
            amount = payload["amount"]
            account = payload.get("account", "checking")
            bal = conn.execute(
                "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
            ).fetchone()
            if bal is None:
                return {"ok": False, "reason": f"No cash account '{account}'."}
            after = bal["balance"] - amount
            # CC-OPS-36 first: a negative balance is impossible regardless of what
            # the policy floor is set to. The floor is policy and can be edited;
            # this one cannot.
            if after < 0:
                return {
                    "ok": False,
                    "reason": f"Refused: ${amount:,.2f} exceeds the ${bal['balance']:,.2f} "
                              f"in '{account}'. The balance may never go negative "
                              f"(CC-OPS-36), and no revenue is modelled.",
                    "balance_now": bal["balance"],
                    "shortfall": round(amount - bal["balance"], 2),
                }
            if after < CASH_FLOOR:
                return {
                    "ok": False,
                    "reason": f"Approving would leave ${after:,.2f}, below the "
                              f"${CASH_FLOOR:,.0f} reserve floor (CC-OPS-2).",
                    "balance_now": bal["balance"],
                    "balance_if_approved": round(after, 2),
                    "override": "Lower the floor in policy or reject this item; "
                                "the server will not execute a floor breach.",
                }
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?,?,?,?,?,?)",
                (payload["kind"], payload["ref_id"], amount, account, _shop_today(), approved_by),
            )
            conn.execute(
                "UPDATE cash_accounts SET balance = ? WHERE name = ?", (round(after, 2), account)
            )
            marked_paid = None
            still_owed = None
            if payload["kind"] == "invoice":
                inv = conn.execute(
                    "SELECT amount FROM invoices WHERE id = ?", (payload["ref_id"],)
                ).fetchone()
                paid_total = conn.execute(
                    "SELECT COALESCE(SUM(amount), 0.0) AS s FROM payments "
                    "WHERE kind = 'invoice' AND ref_id = ?", (payload["ref_id"],)
                ).fetchone()["s"]
                # An invoice is only settled once it is settled in full. Marking it
                # paid on a partial payment would silently unblock the vendor under
                # CC-OPS-35 while money is still owed — the shop would believe it
                # could reorder when the vendor would still refuse.
                if inv is not None and paid_total + 1e-9 >= inv["amount"]:
                    conn.execute(
                        "UPDATE invoices SET status = 'paid' WHERE id = ?", (payload["ref_id"],)
                    )
                    marked_paid = payload["ref_id"]
                elif inv is not None:
                    still_owed = round(inv["amount"] - paid_total, 2)
            executed = {
                "payment_id": cur.lastrowid,
                "account": account,
                "balance_before": bal["balance"],
                "balance_after": round(after, 2),
                "invoice_marked_paid": marked_paid,
                "invoice_still_owed": still_owed,
                "partial_payment_note": (
                    f"Partial payment recorded. Invoice #{payload['ref_id']} still owes "
                    f"${still_owed:,.2f} and remains open, so the vendor stays blocked "
                    f"under CC-OPS-35."
                ) if still_owed else None,
            }
        elif row["kind"] == "purchase_order":
            executed = {
                "note": "PO approved and sent to the vendor. Inventory is unchanged until "
                        "goods are received.",
                "earliest_delivery_day": payload.get("earliest_delivery_day"),
            }
        elif row["kind"] == "customer_message":
            executed = {"note": "Message approved for sending by a human.",
                        "to": payload.get("to")}

        conn.execute(
            "UPDATE pending_approvals SET status='approved', decided_by=?, decided_at=?, "
            "decision_note=? WHERE id=?",
            (approved_by, _now(), note, approval_id),
        )
        conn.commit()
        return {"ok": True, "approval_id": approval_id, "status": "approved",
                "kind": row["kind"], "decided_by": approved_by, "executed": executed}
    finally:
        conn.close()


def _blocking_approvals(conn: sqlite3.Connection, ticket: sqlite3.Row) -> list[dict]:
    """Pending approvals that resolve this ticket, whatever ticket they were filed under.

    An agent working ticket A can legitimately queue the action that resolves
    ticket B — Accounting asked about cash while working the customer order will
    queue the rent payment and tag it with the ticket it had in hand. Matching on
    pending_approvals.ticket_id alone therefore lets ticket B close while the work
    that resolves it is still unapproved. Match on what the action *refers to* as
    well: the lease, the invoice, or the product the ticket names.
    """
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM pending_approvals WHERE status = 'pending'"
    ).fetchall()]
    blocking = []
    for r in rows:
        try:
            payload = json.loads(r["payload"])
        except (ValueError, TypeError):
            payload = {}
        why = None
        if r["ticket_id"] == ticket["id"]:
            why = "filed against this ticket"
        elif (payload.get("kind") == "rent" and ticket["lease_id"] is not None
              and payload.get("ref_id") == ticket["lease_id"]):
            why = f"pays rent on lease {ticket['lease_id']}, which this ticket is about"
        elif (payload.get("kind") == "invoice" and ticket["invoice_id"] is not None
              and payload.get("ref_id") == ticket["invoice_id"]):
            why = f"pays invoice #{ticket['invoice_id']}, which this ticket is about"
        elif (r["kind"] == "purchase_order" and ticket["sku"]
              and payload.get("sku") == ticket["sku"]
              and (ticket["size"] is None or payload.get("size") == ticket["size"])):
            why = f"restocks {ticket['sku']} {ticket['size'] or ''}".strip()
        if why:
            blocking.append({"approval_id": r["id"], "kind": r["kind"],
                             "summary": r["summary"], "amount": r["amount"],
                             "filed_under_ticket": r["ticket_id"], "blocks_because": why})
    return blocking


@mcp.tool
def close_ticket(ticket_id: int, resolution: str, closed_by: str) -> dict:
    """Mark a ticket resolved, recording who closed it and why (CC-OPS-23).

    Only Boss closes tickets; a specialist may not. A ticket with actions still
    awaiting human approval cannot be closed — that would hide an unfinished
    decision from the person who still has to make it.
    """
    if not resolution.strip():
        return {"ok": False, "reason": "resolution must say what was decided."}
    conn = _connect_rw()
    try:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"ok": False, "reason": f"No ticket {ticket_id}."}
        if t["status"] != "open":
            return {"ok": False, "reason": f"Ticket {ticket_id} is already '{t['status']}'."}
        blocking = _blocking_approvals(conn, t)
        if blocking:
            elsewhere = [b for b in blocking if b["filed_under_ticket"] != ticket_id]
            return {
                "ok": False,
                "reason": f"Ticket {ticket_id} has {len(blocking)} action(s) awaiting human "
                          f"approval; it cannot be closed yet (CC-OPS-1).",
                "pending_count": len(blocking),
                "blocking_approvals": blocking,
                "note": (
                    f"{len(elsewhere)} of these was filed under another ticket but still "
                    f"resolves this one. An approval queued elsewhere is still unfinished "
                    f"work on this ticket."
                ) if elsewhere else None,
            }
        note = f"{t['notes'] or ''}\n[{_shop_today()}] closed by {closed_by}: {resolution}".strip()
        conn.execute("UPDATE tickets SET status='resolved', notes=? WHERE id=?", (note, ticket_id))
        conn.commit()
        return {"ok": True, "ticket_id": ticket_id, "status": "resolved",
                "closed_by": closed_by, "resolution": resolution}
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs operations MCP server")
    parser.add_argument("--http", action="store_true",
                        help="Serve Streamable HTTP on port 8001 (keeps FastAPI free on 8000)")
    args = parser.parse_args()
    _connect_rw().close()  # ensure the approval queue table exists before serving
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()
