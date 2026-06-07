# Bill.com v3 API Endpoints Reference

## Base URLs
- Production: `https://gateway.prod.bill.com/connect`
- Sandbox:    `https://gateway.stage.bill.com/connect`

## Env Vars (from ~/Projects/billcom-ap-priority/.env)
- `BILLCOM_DEV_KEY`
- `BILLCOM_USERNAME`
- `BILLCOM_API_TOKEN` — used as the `password` field for both v3 login and v2 GL/Class lookup
- `BILLCOM_ORG_ID`
- `BILLCOM_ENVIRONMENT` (`production` | `stage`)

---

## Auth

### POST /v3/login

> ⚠️ **`devKey` must be in the JSON body for this endpoint** — NOT as an HTTP header. Passing it as a header returns `{"message": "devKey: must not be null"}`. All other endpoints use `devKey` as a header.

Always load credentials via `source ~/Projects/billcom-ap-priority/.env` in the shell. Do NOT read/copy-paste credential values — the file may use shell-interpolated values that appear truncated when read as plain text.

Body: `{ username, password, organizationId, devKey }`  
Response: `{ sessionId, userId, organizationId, trusted, ... }`  
TTL: 35 min inactivity. Re-auth on 401.

> ⚠️ **`trusted: false`** in the login response indicates API token auth. This is normal and expected — it does not restrict bill read/approve/deny access, but it does break the `pending-user-approvals` endpoint (see below).

---

## Bills

### GET /v3/bill-approvals/pending-user-approvals

> ❌ **Broken with API token auth.** When using an API token, the session resolves to a system user entity (`syu0...`) instead of a regular user (`006...`). This endpoint validates entity type and returns `BDC_1302: The entity type of id syu0... does not match any of the expected entity types: User.`

**Use this workaround instead:**

```
GET /v3/bills?filters=approvalStatus:eq:ASSIGNED&sort=createdTime:desc&max=20
```

Returns the 20 most recently created ASSIGNED (pending approval) bills. The `ASSIGNED` approval status is the correct filter value — `PENDING`, `PENDING_APPROVAL`, and `NEEDS_APPROVAL` are all unsupported filter values and return a 400 error.

> ⚠️ Do NOT paginate all pages upfront to count totals. The ASSIGNED bucket may contain hundreds of old unresolved bills. Always fetch the 20 newest (`sort=createdTime:desc`) and start enrichment immediately.

### GET /v3/bills/{billId}?billApprovals=true
Full bill detail.

Key fields:
- `id`, `vendorId`, `amount`, `dueDate`
- `invoice.invoiceNumber`, `invoice.invoiceDate`
- `billLineItems[]` — `{ id, amount, description, quantity, price }`
- `paymentStatus` — UNPAID / PAID / SCHEDULED
- `approvalStatus` — UNASSIGNED / ASSIGNED / APPROVED / DENIED
- `approvers[]` — `{ userId, status, approverOrder, statusChangedTime }`
- `description`, `createdTime`, `updatedTime`
- `fundingAmount`, `exchangeRate` (international vendors only)

### GET /v3/bills
List bills with filters.

Query params:
- `filters=vendorId:eq:{vendorId}`
- `sort=createdTime:desc`
- `max=20` (up to 100)
- `page=1`

Filter operators: `eq`, `neq`, `gte`, `lte`, `gt`, `lt`, `contains`

> ⚠️ **v3 list response key:** Bill list endpoints return records under the `results` key, NOT `bills`. Always use `response.get("results", [])` when parsing list responses. Using `bills` will return an empty list and incorrectly trigger NEW_VENDOR and history-based flags.

### PATCH /v3/bills/{billId}
Update bill details including line item descriptions.

Key use case: updating a vague or missing line item description while preserving GL classifications.

```json
{
  "billLineItems": [{
    "id": "bli01...",
    "amount": 191.14,
    "description": "Updated description here",
    "classifications": {
      "chartOfAccountId": "0ca01...",
      "accountingClassId": "cls01..."
    }
  }]
}
```

> ⚠️ Always include `classifications` when patching line items — omitting it will clear the GL account and class assignments.

Success: HTTP 200, returns updated bill object.

### POST /v3/bill-approvals/actions
Approve or deny bills.

Body:
```json
[
  {
    "billId": "00n...",
    "action": "APPROVE",
    "comment": "Approved via AP review agent"
  }
]
```

`action`: `APPROVE` | `DENY`  
`comment`: optional but recommended for audit trail.  
Success: HTTP 200

---

## Vendors

### GET /v3/vendors/{vendorId}
Key fields: `id`, `name`, `email`, `status`, `paymentMethod`, `createdTime`, `address`, `combinePayments`

### GET /v3/vendors
Supports same filter/sort/page params as bills.

---

## Users

### GET /v3/users
Filter: `?filters=role.type:eq:"APPROVER"&sort=createdTime:desc`  
Roles: ADMINISTRATOR, ACCOUNTANT, APPROVER, PAYER, CLERK

---

## GL Account & Class Name Resolution

The v3 API returns IDs only for `chartOfAccountId` and `accountingClassId` on line items. Name resolution requires the v2 API.

### v2 Login (for GL/Class lookup only)

Use `BILLCOM_API_TOKEN` as the `password` field:
```json
POST /v3/login
{ "devKey": "...", "organizationId": "...", "username": "...", "password": "<BILLCOM_API_TOKEN>" }
```

### POST https://api.bill.com/api/v2/List/ChartOfAccount.json
### POST https://api.bill.com/api/v2/List/ActgClass.json

Required form body (NOT JSON-encoded request wrapper):
```
devKey=<BILLCOM_DEV_KEY>
sessionId=<sessionId>
data={"start":0,"max":999}
```

> ⚠️ The `data` value must be a JSON-encoded string. Do NOT use a `request` wrapper. Do NOT form-encode `start`/`max` directly as top-level params.

Response: `response_data` array of `{ id, name, accountType }` objects.

Build `coa_map` and `cls_map` dicts at session start. Cache for the full session.

## Rate Limits
- 429 → back off 5s minimum before retry
- Default page size: 20; max: 100
- Avoid tight loops; fetch enrichment data per bill, not all at once
