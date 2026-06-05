# Bill.com v3 API Endpoints Reference

## Base URLs
- Production: `https://gateway.prod.bill.com/connect`
- Sandbox:    `https://gateway.stage.bill.com/connect`

## Env Vars (from ~/Projects/billcom-ap-priority/.env)
- `BILLCOM_DEV_KEY`
- `BILLCOM_USERNAME`
- `BILLCOM_PASSWORD` (v3 login)
- `BILLCOM_API_TOKEN` (v2 legacy — keep for reference)
- `BILLCOM_ORG_ID`
- `BILLCOM_ENVIRONMENT` (`production` | `stage`)

---

## Auth

### POST /v3/login
Headers: `devKey`  
Body: `{ username, password, organizationId }`  
Response: `{ sessionId, userId, organizationId, ... }`  
TTL: 35 min inactivity. Re-auth on 401.

---

## Bills

### GET /v3/bill-approvals/pending-user-approvals
Returns bills pending approval for the signed-in user.  
Required roles: Administrator, Accountant, Approver.

Response:
```json
{
  "bills": [
    { "billId": "00n...", "vendorId": "009...", "amount": 1500.00, "dueDate": "2026-12-31" }
  ]
}
```

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

Use `BILLCOM_API_TOKEN` as the password field (not `BILLCOM_PASSWORD`):
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
