# AP Analysis Rules — Detailed Reference

## Building the Vendor Baseline

Fetch up to 20 most recent bills for the vendor (excluding the current bill under review).

Compute:
- `count` — number of historical bills found
- `avg` — mean of all historical amounts
- `max` — highest single amount ever
- `trailing6avg` — mean of the 6 most recent amounts (or all available if fewer than 6)
- `lastBillDate` — createdTime of the most recent historical bill
- `last7dayCount` — count of bills from this vendor in the last 7 days
- `invoiceNumbers[]` — all historical invoice numbers for duplicate detection

---

## History Tier Fallback

| count   | Behavior |
|---------|----------|
| 0       | NEW_VENDOR only. Skip all amount-comparison flags. |
| 1–2     | NEW_VENDOR. Amount flags require count >= 3 — still skipped. Max shown for display only. |
| 3–5     | THIN_HISTORY. trailing6avg = mean of all available bills. Amount flags enabled. |
| 6–9     | THIN_HISTORY. Full trailing 6-bill average. Amount flags fully enabled. |
| 10–19   | No THIN_HISTORY. Full analysis on available data. |
| 20+     | Full analysis. trailing6avg from the most recent 6 of the full dataset. |

---

## Flag Definitions

### 🔴 HOLD — requires typed `APPROVE` to override

**DUPLICATE_INVOICE**
- Condition: `invoice.invoiceNumber` is non-null AND exists in `invoiceNumbers[]`
- Message: "Invoice number {X} was already used on a bill from {date}. Possible duplicate billing."

**EXTREME_AMOUNT_SPIKE**
- Condition: `amount > trailing6avg * 2.0` AND `count >= 3`
- Message: "Amount is {X}% above the vendor's trailing average of ${avg}. This is unusually high."

---

### 🟡 REVIEW — advisory, does not block approval

**THIN_HISTORY**
- Condition: `count >= 3 AND count <= 9`
- Message: "Only {count} prior bill(s) on record. Small sample — apply extra scrutiny to any flags."

**AMOUNT_SPIKE**
- Condition: `amount > trailing6avg * 1.25` AND `count >= 3`
- Message: "Amount is {X}% above trailing average of ${avg}."
- Skip if EXTREME_AMOUNT_SPIKE already triggered.

**ALL_TIME_HIGH**
- Condition: `amount > max` AND `count >= 1`
- Message: "Highest bill ever from this vendor. Previous max was ${max}."

**MISSING_INVOICE_NUMBER**
- Condition: `invoice.invoiceNumber` is null or empty
- Message: "No invoice number. Required for record-keeping and duplicate detection."

**MISSING_INVOICE_DATE**
- Condition: `invoice.invoiceDate` is null or empty
- Message: "No invoice date provided."

**PAST_DUE**
- Condition: `dueDate` < today
- Message: "Due date {date} has already passed. Payment will be late."

**RUSHED_DUE_DATE**
- Condition: `dueDate` is within 3 calendar days of today AND `dueDate` >= today
- Message: "Due in {N} day(s). Tight window — confirm urgency before approving."

**NEW_VENDOR**
- Condition: vendor `createdTime` < 30 days ago OR `count < 3`
- Message: "Limited history for this vendor ({count} prior bill(s)). Verify legitimacy."

**VAGUE_LINE_ITEMS**
- Condition: any `billLineItem.description` is null, empty, or fewer than 5 characters
- Message: "Line item #{N} has no or insufficient description."

**ROUND_NUMBER**
- Condition: `amount >= 500` AND `amount % 1 == 0` AND (`amount % 100 == 0` OR `amount % 500 == 0` OR `amount % 1000 == 0`)
- Message: "Suspiciously round number. Could indicate estimated or split billing — verify the invoice."
- Always append: "May be normal for retainer or subscription-based vendors."

**FREQUENCY_SPIKE**
- Condition: `last7dayCount >= 2` (2+ other bills from same vendor in last 7 days)
- Message: "{N} other bill(s) from this vendor in the last 7 days. Unusual volume."

---

## Scoring & Severity

1. Any HOLD flag → 🔴 HOLD
2. Any REVIEW flag → 🟡 REVIEW
3. None → 🟢 CLEAN

Always list all flags. Never suppress lower-severity ones when a higher one fires.

---

## Notes & Comment Passthrough

- Notes stored in session memory keyed by `billId`
- Multiple notes on the same bill: append in order, join with ` | `
- On APPROVE: combined notes → `comment`. Default: `"Approved via AP review agent"`
- On DENY: combined notes → `comment`. If none, prompt once (optional). Default: `"Denied via AP review agent"`
- Notes shown in card under `📝 Notes:` after each addition
- Notes appear in session summary under `📝 Annotated Bills:` (only bills that had notes)

---

## Edge Cases

**International vendors:**
- If `exchangeRate` and `fundingAmount` present, show both:
  - "Amount: {amount} {currency} ≈ ${fundingAmount} USD (rate: {exchangeRate})"
- Compare `fundingAmount` (USD) against historical `fundingAmount` values, not raw local-currency `amount`.

**Bulk line items (> 10):**
- Display first 5 in card, summarize: "(+{N} more line items)"
- Still check ALL line items for VAGUE_LINE_ITEMS flag.

**Amounts < $50:**
- Skip ROUND_NUMBER flag (low risk, high noise).
- Skip AMOUNT_SPIKE if trailing avg is also < $50.

**First-time vendor (count == 0):**
- Show: "No payment history found. This appears to be the first invoice from this vendor."
- Only flag: NEW_VENDOR.
