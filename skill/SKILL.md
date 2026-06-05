---
name: billcom-agentic-approver
description: "Agentic AP approver for Bill.com: fetches pending bills, compares to vendor history, flags anomalies, and routes approve/deny decisions via the v3 API."
user-invocable: true
---

# Bill.com Agentic AP Approver

Acts as an experienced AP manager. Reviews every bill pending in the user's Bill.com approval queue, compares each invoice against vendor payment history, flags anomalies, and waits for an approve/deny/skip decision before calling the API.

**Trigger:** user asks to "review bills", "check my Bill.com queue", "AP approvals", or runs `/skill billcom-agentic-approver`.

---

## Setup — Credentials

Before the first API call, resolve credentials in this order:

1. Check for existing `.env` file at `~/Projects/billcom-ap-priority/.env` and load it.
2. Fall back to env vars: `BILLCOM_DEV_KEY`, `BILLCOM_USERNAME`, `BILLCOM_API_TOKEN`, `BILLCOM_ORG_ID`, `BILLCOM_ENVIRONMENT`.
3. If any required values are still missing, ask the user once for all missing values.
4. Derive base URL:
   - `production` → `https://gateway.prod.bill.com/connect`
   - `stage`      → `https://gateway.stage.bill.com/connect`

Store resolved values in session memory. Never log credentials or print them.

---

## Authentication

```bash
curl -s -X POST "$BASE_URL/v3/login" \
  -H "Content-Type: application/json" \
  -H "devKey: $BILLCOM_DEV_KEY" \
  -d "{\"username\":\"$BILLCOM_USERNAME\",\"password\":\"$BILLCOM_API_TOKEN\",\"organizationId\":\"$BILLCOM_ORG_ID\"}"
```

Extract `sessionId` from response. Sessions expire after 35 min of inactivity — re-auth transparently on any 401.

Use `sessionId` + `devKey` headers on every subsequent request.

> ⚠️ **Auth note:** Use `BILLCOM_API_TOKEN` as the `password` field for both v3 login and v2 GL/Class lookup. This is Bill.com’s recommended approach for programmatic access — the API token can be rotated independently of the account password. If login returns 401, verify the token is active in Bill.com → Settings → API.

---

## Workflow

### Step 1 — Fetch Pending Queue

```bash
GET $BASE_URL/v3/bill-approvals/pending-user-approvals
Headers: sessionId, devKey
```

Response: `{ "bills": [ { "billId", "vendorId", "amount", "dueDate" }, ... ] }`

If the list is empty → tell the user "No bills pending your approval." and stop.

Show a summary count first: `"Found N bill(s) pending your approval."`

---

### Step 2 — Enrich Each Bill

For each bill in the queue, fetch:

**A. Full bill details:**
```bash
GET $BASE_URL/v3/bills/{billId}?billApprovals=true
```
Captures: `invoiceNumber`, `invoiceDate`, `billLineItems`, `approvalStatus`, `approvers`, `description`, `paymentStatus`.

**B. Vendor details:**
```bash
GET $BASE_URL/v3/vendors/{vendorId}
```
Captures: `name`, `email`, `address`, `paymentMethod`, `createdTime`.

**D. GL Account & Class lookup (run once per session, before first bill card):**

The v3 API returns `chartOfAccountId` and `accountingClassId` on line items but does not expose endpoints to resolve them by name. Use the v2 API with the **`data` JSON wrapper pattern**:

```python
# Login: use BILLCOM_API_TOKEN as the password field
login_resp = POST v3/login with password=BILLCOM_API_TOKEN
sid = login_resp["sessionId"]

# Fetch COA and Classes via v2 (data wrapper pattern)
for entity in ["ChartOfAccount", "ActgClass"]:
    POST https://api.bill.com/api/v2/List/{entity}.json
    form body: devKey=..., sessionId=..., data=json.dumps({"start":0,"max":999})
```

> ⚠️ **Critical v2 pattern:** Pass `devKey` and `sessionId` as top-level form fields, and the query params (`start`, `max`, `filters`) as a JSON-encoded string under the `data` key. Do NOT use a `request` wrapper or direct form-encoded integers — both will fail.

Build two lookup dicts at session start:
- `coa_map`: `{ chartOfAccountId → name }` (453 entries typical)
- `cls_map`: `{ accountingClassId → name }` (21 entries typical)

Cache for the full session — do not re-fetch per bill.

**C. Vendor payment history (last 20 bills):**
```bash
GET $BASE_URL/v3/bills?filters=vendorId:eq:{vendorId}&sort=createdTime:desc&max=20
```
Use to build the historical baseline. See `references/analysis-rules.md` for fallback tiers.

> ⚠️ **Critical:** The v3 bill list response returns records under the key `results`, NOT `bills`. Always parse with `response.get("results", [])`. Using `bills` silently returns an empty list and will cause false NEW_VENDOR and history flags.

---

### Step 3 — AP Analysis

Run all flags defined in `references/analysis-rules.md`. Assign severity:
- 🔴 **HOLD** — duplicate invoice or amount > 200% of trailing average
- 🟡 **REVIEW** — any other flag
- 🟢 **CLEAN** — no flags

---

### Step 4 — Present Bill Card

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 BILL REVIEW  [{index}/{total}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Vendor:       {vendorName}
Invoice #:    {invoiceNumber}
Invoice Date: {invoiceDate}
Due Date:     {dueDate}
Amount:       ${amount}
Line Items:
  • {description | "(no description)"} — ${lineAmount}
    GL: {chartOfAccountName}  |  Class: {accountingClassName}
  • ...

📊 VENDOR HISTORY
  Bills on file: {count}
  Avg amount:    ${avg}
  Max ever:      ${max}
  Last bill:     {date} — ${lastAmount}

{🟢 CLEAN | 🟡 REVIEW | 🔴 HOLD}
{Each flag — emoji + plain-English explanation}

📝 Notes: {notes added this session, or "(none)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A] Approve  [D] Deny  [N] Note  [S] Skip  [Q] Quit
```

**Decision inputs:**
- `a`, `approve`, `yes`, `y` → APPROVE
- `d`, `deny`, `reject`, `no` → DENY
- `n`, `note` → ADD NOTE (see Step 4a)
- `s`, `skip` → defer, no API call, bill stays in queue
- `q`, `quit`, `done` → end session

**🔴 HOLD override:** require the user to type `APPROVE` in full to confirm. `a` or `y` alone are rejected.

---

### Step 3a — Updating Line Item Descriptions

If a line item has no description or a vague one (VAGUE_LINE_ITEMS flag), the agent may:
1. Research the vendor's service offerings if needed (web search) to understand what the charge covers
2. Rewrite the description clearly and concisely for an executive audience — preserving all service names and specifics
3. Patch the bill before presenting the card:

```bash
PATCH $BASE_URL/v3/bills/{billId}
Body: {
  "billLineItems": [{
    "id": "{lineItemId}",
    "amount": {amount},
    "description": "{rewritten description}",
    "classifications": { ...preserve existing chartOfAccountId and accountingClassId... }
  }]
}
```

> ⚠️ Always preserve `classifications` (chartOfAccountId and accountingClassId) when patching line items or they will be cleared.

Show the updated description in the bill card. The VAGUE_LINE_ITEMS flag may be noted as resolved in the card if the description was successfully updated.

---

### Step 4a — [N] Notes

Notes can be added at any point — before, after, or instead of a decision. They are never destructive on their own.

1. User types `n` or `note`
2. Prompt: `"Add note for {vendorName} ${amount} — type your note:"`
3. **Always rewrite the note** for clarity and concision before saving. The audience is executive-level. Rules:
   - Fix grammar, spelling, and capitalization
   - Remove filler words and redundancy
   - Use active voice and tight phrasing
   - Preserve all factual content — never drop names, amounts, or specifics
   - Show the rewritten version to the user before saving: `"Rewritten note: {rewritten}"` — proceed automatically without asking for confirmation unless it changes the meaning significantly
4. **If the note contains any @mention** (e.g. `@JaneSmith` or `@Jane`):
   - Query `GET $BASE_URL/v3/users?max=100` to fetch all org users
   - Fuzzy-match the mention text against each user's `firstName`, `lastName`, and `firstName + ' ' + lastName`
   - If exactly one match is found: replace the raw @mention with `@{firstName} {lastName}` (correct full name with space)
   - If multiple matches: list them and ask the user to clarify
   - If no match: warn `"Could not find a Bill.com user matching '{mention}' — note will be saved as-is"`
4. Store the resolved note in session memory keyed by `billId`
5. Redisplay card with note under `📝 Notes:`
6. Re-present decision menu

> ⚠️ **Notification caveat:** Bill.com API `comment` fields are plain text. An @mention in a comment does NOT trigger an in-app or push notification to that user. It is a documentation/audit trail reference only. If the tagged person needs to take action, follow up via a separate channel (email, Slack, etc.) and let the user know.

**Multiple notes:** appended in order, joined with ` | ` when passed to the API.
**On Approve:** note → `comment` field. Default if no note: `"Approved via AP review agent"`.
**On Deny:** note → `comment`. If no note, prompt once (optional, Enter to skip). Default: `"Denied via AP review agent"`.
**Session summary:** lists all annotated bills.

---

### Step 5 — Execute Decision

**Approve:**
```bash
POST $BASE_URL/v3/bill-approvals/actions
Body: [{"billId": "{billId}", "action": "APPROVE", "comment": "{note or default}"}]
```

**Deny:**
```bash
POST $BASE_URL/v3/bill-approvals/actions
Body: [{"billId": "{billId}", "action": "DENY", "comment": "{note or default}"}]
```

Confirm with: `"✅ Approved: {vendorName} ${amount}"` or `"❌ Denied: {vendorName} ${amount}"`.

On API error: show the error clearly, ask user to retry or skip.

---

### Step 6 — Session Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 AP REVIEW COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reviewed: N bills
Approved: N  ($total)
Denied:   N  ($total)
Skipped:  N

📝 Annotated Bills:
  • {vendorName} ${amount} — "{note}"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Omit Annotated Bills section if no notes were added.

---

## Error Handling

- **401** → re-authenticate silently, retry once. If still failing, tell user.
- **404** → note "Data unavailable" in card; user can still decide.
- **429** → wait 5s, retry. If persists, pause and notify user.
- **Network error** → show error, ask to retry or quit.

---

## AP Manager Principles

- Be direct. Flag issues clearly; don't bury them.
- Never approve on behalf of the user — always wait for explicit input.
- For ambiguous flags (round numbers, retainers), add context.
- THIN_HISTORY is advisory — state the sample size.
- HOLD flags are serious until the user explicitly overrides them.
