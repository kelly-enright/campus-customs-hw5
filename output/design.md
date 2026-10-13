# Campus Customs — Operations Desk, Design

**Concept: the back office of the 1936 shop.** HW 4 dressed the storefront as a
game-day football program — aged paper, Alfa Slab One headlines, Oswald
condensed numerals, navy ink and oxblood on cream, Handsome Dan throughout. This
is the room behind that storefront: a dispatcher's desk where tickets land in a
wire tray, five staff work them in their own hands, and a cash drawer sits under
the counter on green felt.

Same ink, same paper, same brass. Different furniture, because this is a working
room rather than a printed program — so the surfaces are desk blotter and card
stock instead of newsprint, and the motion is mechanical rather than editorial.

---

## Layout: a desk, not a dashboard

Three columns, and the order is the argument:

```
   IN TRAY            THE FLOOR + THE WIRE            YOUR DESK
   work arrives   →   work gets done             →    work needs you
                      THE DOCKET                       CASH DRAWER
```

Work moves left to right, which is how a desk actually reads. A conventional
dashboard would put four equal cards in a grid and leave the reader to work out
the order; this says plainly that things arrive on the left, happen in the
middle, and end up needing a signature on the right.

Below 1150px it collapses to one column in that same order, so the narrative
survives on a laptop.

### Why the middle column is widest

The middle holds the two things a person actually watches — the floor and the
wire — and it is sized to be the natural focus. The in-tray is narrow because a
ticket is a glance; the right column is narrow because approvals are short and
the cash figure wants to be read, not studied.

---

## How the agents read differently

The brief asked that agents read differently. A coloured dot per agent would
satisfy that literally and fail in practice: once five dots are on screen, a
reader is matching colours to a legend instead of reading.

So each agent gets **its own stationery** — colour, typeface and paper stock:

| Agent | Hand | Paper | Colour | Why |
|---|---|---|---|---|
| **Boss** | Alfa Slab One | cream | navy | The slab display face is the masthead's own. Boss speaks for the shop |
| **Inventory** | Oswald condensed | buff card | ochre | Condensed figures are how stock cards and count sheets are set |
| **Accounting** | IBM Plex Mono | pale green | ledger green | Tabular monospace — numbers that line up in columns |
| **Facilities** | Oswald condensed | lilac | plum | Civic and clerical, like a lease rider |
| **Customer Service** | Special Elite | warm off-white | oxblood | A typewriter face: these are letters, and they are drafts |

The effect is that a wall of events is scannable without labels. Accounting's
monospace ledger line never reads as Customer Service's typewritten draft, even
at a glance and even in peripheral vision. Each desk also carries a single
stamped initial — B, I, A, F, C — as a quick visual anchor.

### The floor

Five desks. An idle agent is dimmed to 62%; a working agent lifts 3px, gains a
ring in its own colour, grows a travelling underline, and shows a nib ✒ bobbing
in the corner. Underneath, each desk reports what it is doing *right now* in
plain language — "looking up check stock", "asked accounting" — plus a running
count of lookups.

### Who asked whom

The fully connected team is the point of the assignment, and a list of events
never shows it. So delegations are drawn as **threads of ink between desks**:
two agent pips joined by a gradient running from the asker's colour to the
answerer's, with the question alongside, indented by delegation depth.

**A refused or timed-out hand-off draws as a broken red dash** rather than
disappearing. When Facilities tries to ask Accounting and CC-OPS-27 refuses the
cycle, that refusal is the system working, and it belongs on screen where a
person can see it happen.

---

## The wire

A teletype, not a log viewer. Fixed-width elapsed stamps down the left, a
perforated tear strip across the top, and each line arriving with a slide rather
than appearing. Lines are written in the acting agent's own hand on a left
border in its colour.

Three details carry most of the weight:

- **Rule chips.** Any CC-OPS rule an entry cites is set as a small brass-edged
  chip. On this desk *why* matters as much as *what* — a refusal that cites
  CC-OPS-27 is a rule holding, and burying it in body text wastes it.
- **Cached lookups are tinted amber and marked "cached."** The per-run tool
  cache cut wall clock by 43%; showing a reused answer rather than hiding it
  makes the system's thrift visible instead of making it look idle.
- **Tail-following is conditional.** The feed scrolls to the newest line only
  when the reader is already at the bottom. Yanking someone back down while they
  read an earlier line is hostile.

---

## Resolved tickets, and the stamps

Status is a **rubber stamp**, pressed on at a slight angle with a doubled ragged
edge — not a pill from a UI kit. `OPEN` in blue, `RESOLVED` in ledger green at a
steeper tilt, `● WORKING` in crimson, `REFUSED` in stamp red.

The `stamp-in` animation lands them: scale 2.6 → 0.94 → 1.04 → 1, rotating into
place over 420ms. A resolved ticket gets **stamped**, which is both more
satisfying and more legible than a row quietly changing colour.

A resolved ticket **stays in the tray** rather than vanishing. The desk's job is
to show the day's work, and work that is finished is still work that happened.

Ticket cards are docket cards: a punch hole top-right, a 6px colour spine, and a
7px slide toward the reader with a deepened shadow when selected — the card
being pulled forward out of the stack.

---

## Cash

The cash drawer is the only element not on paper: dark green felt, under the
counter, where cash lives.

- **The balance counts down digit by digit** over 900ms with a cubic ease when it
  drops, and flashes crimson while falling. The brief asked that the balance
  visibly drop after an approved payment; a figure that simply swaps from $3,400
  to $1,000 is easy to miss, and one that rolls down makes a person look up.
- **It flashes on the way down and never on the way up**, because in this shop
  money only leaves (CC-OPS-36). The strip under it says so in words:
  "↓ outflow only — no revenue modelled."
- **The reserve floor is drawn as a line the balance must not cross** — a brass
  marker on the bar, with the fundable portion in green. The $500 floor is the
  single constraint the whole board turns on, so it is drawn rather than stated.
- **Claims against it are listed in priority order** with P1/P2 chips, overdue
  items flagged in brass, and anything the floor blocks set in warning red.

When not everything can be paid, the drawer says so plainly: *"Not everything
here can be paid without breaking the floor. The red line is a decision for you,
not for the agents."*

---

## Your desk — approvals

The approval tray is deliberately the **heaviest** thing on screen, because it is
the one place a person changes the world.

- **Payments sit on ledger-ruled paper** — real repeating rules at 25px, the
  amount in 25px tabular figures in ledger green.
- **Letters are carbon copies** — warm off-white stock, Special Elite throughout,
  and "Read letter" opens the actual drafted text rather than a JSON blob.

Those two must not look alike. Approving a $2,400 payment and approving a letter
are different acts, and a uniform row of buttons would imply they were the same.

- **"Signing as" sits above the queue.** The name goes on the payment record, and
  the note under the field says an agent's name is never accepted there. Approve
  is disabled until it is filled.
- **A refusal renders in place, as an explanation.** When the server returns 409
  because a payment would breach the floor, the card grows a stamped red panel
  with the reason and the suggested override. It is not a toast and not an error
  colour — the shop's rules declining is the system working, and the reason is
  the most useful thing on screen at that moment.

---

## The docket

When a run finishes, a docket appears: Boss's conclusion in a pull quote, then
**one sentence per agent in that agent's own hand** saying what it checked and
who it asked.

Below that, a brass panel: **"Guardrails that fired — the system holding, not
failing."** Refused cycles, absorbed timeouts, exhausted budgets. This is the
safety work made visible; without it, a person watching would never know the
system had held.

---

## Motion

Mechanical rather than editorial — paper and drawers, not floating cards.

| Animation | Where | Why |
|---|---|---|
| `stamp-in` | status stamps | overshoot and settle, like a stamp pressed and lifted |
| `drop-in` | ticket cards, docket | papers landing in a tray, staggered 70–80ms |
| `slide-in` | wire lines, mesh threads | the teletype advancing |
| count-down | cash balance | money visibly leaving |
| `writing` | nib on a working desk | someone is actually writing |
| `blink` | live dots | a wire that is live |

All of it is behind `prefers-reduced-motion: reduce`.

---

## Handsome Dan

Carried over from HW 4, asleep under the desk with drifting z's. **He wakes when
the team is working** — eyes open, head tilting, tail wagging.

Two reasons. Continuity: the storefront and the back office are the same
business, and the mascot is the cheapest way to say so. And the idle state needs
to be something other than blank — a sleeping dog is a nicer empty state than a
grey box, and his waking is a second, peripheral signal that the team is running.

---

## Creative choices worth naming

1. **Stationery instead of colour-coding.** Five typefaces on five papers, so
   the agents are legible as people rather than as categories.
2. **The mesh drawn as ink threads**, with refusals as broken red dashes — the
   full-connectivity claim made visible, including when it is correctly denied.
3. **Rule citations as brass chips** everywhere a rule applies, so the policy is
   part of the interface rather than hidden in the backend.
4. **A cash drawer that counts down and flashes only downward**, encoding
   CC-OPS-36 in the motion itself.
5. **The reserve floor drawn as a line, not stated as a number.**
6. **Refusals rendered as explanations, not errors** — a 409 is the shop working.
7. **Two kinds of paper in the approval tray**, so money and letters never read
   as the same decision.
8. **A sleeping dog** who wakes with the team.
9. **Punch holes, tear strips, and perforations** — small physical tells that
   this is a desk with paper on it.
10. **"Agents prepare · only a person approves"** standing in the footer, so the
    governing rule of the whole system is never off screen.

---

## Accessibility

- Contrast: cream on navy ~12:1, ink on paper ~11:1; brass is used for emphasis
  on dark grounds only, never as small text on cream.
- Every control is a real `<button>` or `<input>`; the tray uses `aria-pressed`,
  sections carry `aria-label`, errors use `role="alert"`.
- Focus rings are 3px brass at 2px offset — visible against both paper and
  blotter.
- Status is never colour alone: stamps carry words, the mesh pairs colour with a
  dash pattern, cached entries are labelled as well as tinted.
- All motion respects `prefers-reduced-motion`.
