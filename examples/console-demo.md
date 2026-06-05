# Console Demo — Anonymized Session Example

The following is a representative example of a full AP review session.
All vendor names, invoice numbers, amounts, and user names have been anonymized.

---

## Session Start

```
Found 6 bill(s) pending your approval.
```

---

## Bill 1 of 6

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [1/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       Acme International Goods Co.
Invoice #:    AI-2026001
Invoice Date: 2026-04-01
Due Date:     2026-06-01
Amount:       $12,500.00
Line Items:
  • Product inventory: PO #P-100 — $12,500.00
    GL: Inventory Asset  |  Class: Product Line A

📊 VENDOR HISTORY
  Bills on file: 19
  Avg amount:    $18,400.00
  Max ever:      $62,000.00
  Last bill:     2026-05-14 — $21,000.00

🟡 REVIEW
  ⚠️  PAST_DUE: Due 2026-06-01 — 3 day(s) overdue. Payment will be late.

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** S

---

## Bill 2 of 6

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [2/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       Bloom Creative Studio LLC
Invoice #:    10042
Invoice Date: 2026-06-01
Due Date:     2026-06-01
Amount:       $6,000.00
Line Items:
  • Textile & graphic design — $6,000.00
    GL: Contractor Payments  |  Class: Product Line A

📊 VENDOR HISTORY
  Bills on file: 8
  Avg amount:    $4,675.00
  Max ever:      $6,800.00
  Last bill:     2026-03-05 — $6,800.00

🟡 REVIEW
  ⚠️  THIN_HISTORY: Only 8 prior bill(s) — small sample, apply extra scrutiny.
  ⚠️  AMOUNT_SPIKE: 31% above trailing avg of $4,566.67.
  ⚠️  PAST_DUE: Due 2026-06-01 — 3 day(s) overdue. Payment will be late.
  ⚠️  ROUND_NUMBER: Round number — verify against invoice. (Normal for retainers.)

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** N

```
Add note for Bloom Creative Studio LLC $6,000.00 — type your note:
```

> **User:** @Jane Smith needs to update vendor bank account and routing number before payment

```
Looking up "@Jane Smith" in Bill.com users...
✅ Resolved: @Jane Smith (Accounts Payable Manager)

⚠️  Note: Bill.com API comments are plain text — @mentions do not trigger
    in-app notifications. Follow up with Jane directly if action is needed.

Rewritten note:
"@Jane Smith — Please update vendor bank account and routing number before payment is processed."

📝 Notes: "@Jane Smith — Please update vendor bank account and routing number
           before payment is processed."
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** A

```
✅ Approved: Bloom Creative Studio LLC $6,000.00
```

---

## Bill 3 of 6

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [3/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       Summit Payroll Services LLC
Invoice #:    INV-1000001
Invoice Date: 2026-05-31
Due Date:     2026-05-31
Amount:       $1,056.45
Line Items:
  • Monthly RecordKeeping Fee — $1,056.45
    GL: Payroll Expenses  |  Class: Operations

📊 VENDOR HISTORY
  Bills on file: 19
  Avg amount:    $946.01
  Max ever:      $2,419.20
  Last bill:     2026-05-28 — $387.50

🟡 REVIEW
  ⚠️  AMOUNT_SPIKE: 50% above trailing avg of $705.77.
  ⚠️  PAST_DUE: Due 2026-05-31 — 4 day(s) overdue. Payment will be late.

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** N

```
Add note for Summit Payroll Services LLC $1,056.45 — type your note:
```

> **User:** added 3 new 1099 contractors to the payroll system jeidy flores enrique rosas and pati flores which is why billing went up

```
Rewritten note:
"Added 3 new 1099 contractors to payroll system: J. Flores, E. Rosas, and P. Flores — accounts for the billing increase."
```

> **User:** A

```
✅ Approved: Summit Payroll Services LLC $1,056.45
```

---

## Bill 4 of 6 — 🔴 HOLD

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [4/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       FastShip Logistics Inc.
Invoice #:    260601L099001
Invoice Date: 2026-06-03
Due Date:     2026-06-18
Amount:       $10,135.09
Line Items:
  • Freight for ecommerce — $10,135.09
    GL: Freight-out  |  Class: Product Line A

📊 VENDOR HISTORY
  Bills on file: 19
  Avg amount:    $4,937.33
  Max ever:      $14,337.76
  Last bill:     2026-05-27 — $11,833.58

🔴 HOLD
  🛑 EXTREME_AMOUNT_SPIKE: 100% above trailing 6-bill avg of $5,064.67.

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** S  *(deferred for manual review)*

---

## Bill 5 of 6

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [5/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       CloudPlatform Corp.
Invoice #:    INV-CP-90001
Invoice Date: 2026-05-31
Due Date:     2026-06-15
Amount:       $191.14
Line Items:
  • (no description) — $191.14
    GL: Dues and Subscriptions  |  Class: Product Line A

📊 VENDOR HISTORY
  Bills on file: 17
  Avg amount:    $311.71
  Max ever:      $539.00
  Last bill:     2026-05-04 — $159.64

🟡 REVIEW
  ⚠️  VAGUE_LINE_ITEMS: Line item #1 has no/insufficient description.

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

Agent detects vague line item and researches the vendor's billing structure:

```
🔍 Researching CloudPlatform Corp. billing components...

Line item description updated in Bill.com:
"Monthly platform fees: supplier network subscription, per-order
 transaction processing, and EDI/VAN connectivity for retail partner
 data exchange."
```

> **User:** A

```
✅ Approved: CloudPlatform Corp. $191.14
```

---

## Bill 6 of 6

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [6/6]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       Riverside Safety Supply LLC
Invoice #:    RS-2026001
Invoice Date: 2026-06-03
Due Date:     2026-07-03
Amount:       $119.99
Line Items:
  • Safety Works - First Aid — $119.99
    GL: General and Safety Expense  |  Class: Operations

📊 VENDOR HISTORY
  Bills on file: 19
  Avg amount:    $186.51
  Max ever:      $1,550.00
  Last bill:     2026-05-06 — $119.99

🟢 CLEAN

📝 Notes: (none)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

> **User:** A

```
✅ Approved: Riverside Safety Supply LLC $119.99
```

---

## Session Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AP REVIEW COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reviewed:  6 bills
Approved:  4  ($7,367.03)
Denied:    0
Skipped:   2  (deferred for manual review)

📝 Annotated Bills:
  • Bloom Creative Studio LLC $6,000.00
    "@Jane Smith — Please update vendor bank account and routing
    number before payment is processed."

  • Summit Payroll Services LLC $1,056.45
    "Added 3 new 1099 contractors to payroll system: J. Flores,
    E. Rosas, and P. Flores — accounts for the billing increase."
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
