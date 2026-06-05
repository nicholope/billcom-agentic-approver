# billcom-agentic-approver

> An AI-powered Accounts Payable approver built on [OpenClaw](https://openclaw.ai) — an agentic AI framework for personal and business automation.

This project demonstrates how agentic AI can replace repetitive, judgment-intensive financial workflows. The agent acts as an experienced AP manager: it connects to your Bill.com account, reviews every pending bill in your approval queue, runs a suite of financial analysis checks against vendor payment history, and walks you through each decision — one bill at a time.

No scripts to run. No dashboards to build. You review bills in natural conversation.

---

## What This Solves

AP invoice approval is one of the most common bottlenecks in small-to-midsize finance teams. Approvers are asked to sign off on bills they have little context on, with no visibility into whether the amount is unusual, whether the vendor is new, or whether the invoice number has been submitted before. The result is either rubber-stamping or slow queues.

This agent brings context to every decision:

- How does this bill compare to what we've paid this vendor before?
- Is this amount a spike, or within normal range?
- Has this invoice number been submitted before?
- What GL account and cost class is this hitting?
- Is anything on this bill missing, vague, or overdue?

---

## What Is OpenClaw?

[OpenClaw](https://openclaw.ai) is an agentic AI gateway that runs on your own machine (Mac, Linux, or a self-hosted server). It connects a large language model (Claude, GPT-4, Gemini, or others) to your tools, APIs, files, and messaging apps — and lets you run persistent, stateful AI agents that take real actions on your behalf.

Think of it as a personal AI operating system. Instead of chatting with an AI that only returns text, OpenClaw agents can call APIs, read and write files, schedule jobs, send messages, and chain complex multi-step workflows — all triggered from a simple conversation in Telegram, Discord, or any connected channel.

This project is an **OpenClaw Skill** — a reusable, installable workflow that any OpenClaw user can install and trigger by name.

---

## Features

### 🔍 Intelligent Bill Review
- Fetches your live pending approval queue from Bill.com (`GET /v3/bill-approvals/pending-user-approvals`)
- Enriches each bill with full line item detail, vendor profile, and up to 20 bills of payment history

### 📊 AP Analysis Engine
Runs 11 checks on every bill before you see it:

| Flag | Severity | Condition |
|---|---|---|
| Duplicate Invoice | 🔴 HOLD | Invoice # already used for this vendor |
| Extreme Amount Spike | 🔴 HOLD | > 200% of trailing 6-bill average |
| Thin History | 🟡 REVIEW | 3–9 prior bills (small sample) |
| Amount Spike | 🟡 REVIEW | > 125% of trailing average |
| All-Time High | 🟡 REVIEW | Exceeds vendor's highest ever bill |
| Missing Invoice # | 🟡 REVIEW | No invoice number on record |
| Missing Invoice Date | 🟡 REVIEW | No invoice date provided |
| Past Due | 🟡 REVIEW | Due date has already passed |
| Rushed Due Date | 🟡 REVIEW | Due within 3 days |
| New Vendor | 🟡 REVIEW | < 3 prior bills or created < 30 days ago |
| Vague Line Items | 🟡 REVIEW | Missing or insufficient description |
| Round Number | 🟡 REVIEW | Suspiciously round amount > $500 |
| Frequency Spike | 🟡 REVIEW | 2+ bills from vendor in the last 7 days |

🔴 **HOLD** bills require you to type `APPROVE` in full to override — single-letter shortcuts are rejected.

### 🏷️ GL Account & Cost Class on Every Line Item
- Resolves `chartOfAccountId` and `accountingClassId` from Bill.com's v2 API at session start
- Every line item shows the human-readable GL account name and accounting class — no more opaque IDs

### ✏️ Proactive Line Item Description Enrichment
- When a line item has a vague or missing description, the agent researches the vendor's services and rewrites the description
- Updated directly in Bill.com via `PATCH /v3/bills/{billId}` before the card is presented
- GL classifications are always preserved during patching

### 📝 Notes on Any Bill
- Add a note at any point — before deciding, after deciding, or as a standalone annotation
- Notes are rewritten automatically for clarity and concision for an executive audience
- Notes are passed as the `comment` field on the approval/denial API call for a clean audit trail

### @ User Mention Resolution
- When a note contains an @mention, the agent queries `GET /v3/users` to resolve the correct full name
- Prevents broken mentions from typos or missing spaces (e.g. `@JaneSmith` → `@Jane Smith`)
- Transparently flags that Bill.com API comments are plain text — @mentions do not trigger in-app notifications

### ⌨️ Simple Decision Interface
Each bill presents a clean card with a five-option menu:

| Input | Action |
|---|---|
| `A` | Approve — calls `POST /v3/bill-approvals/actions` with `APPROVE` |
| `D` | Deny — calls the same endpoint with `DENY` + optional comment |
| `N` | Note — add a free-text annotation (can be done multiple times) |
| `S` | Skip — defers the bill, no API call made |
| `Q` | Quit — ends the session, all prior decisions stand |

### 📋 Session Summary
After every session, a clean summary shows total reviewed, approved, denied, skipped, and all annotated bills with their notes.

---

## Architecture

```
User (Telegram / any OpenClaw channel)
        │
        ▼
   OpenClaw Agent  ◄──── SKILL.md (this skill)
        │
        ├── Bill.com v3 API (auth, pending queue, bill detail, vendor detail, approve/deny)
        ├── Bill.com v2 API (GL account + class name resolution)
        └── Web search (vendor research for line item description enrichment)
```

**Key API Endpoints Used**

| Endpoint | Purpose |
|---|---|
| `POST /v3/login` | Session auth (API token as password) |
| `GET /v3/bill-approvals/pending-user-approvals` | Fetch approval queue |
| `GET /v3/bills/{billId}?billApprovals=true` | Full bill detail |
| `GET /v3/bills?filters=vendorId:eq:{id}` | Vendor payment history |
| `GET /v3/vendors/{vendorId}` | Vendor profile |
| `GET /v3/users` | User lookup for @mention resolution |
| `POST /v3/bill-approvals/actions` | Approve or deny |
| `PATCH /v3/bills/{billId}` | Update line item descriptions |
| `POST v2/List/ChartOfAccount.json` | GL account name resolution |
| `POST v2/List/ActgClass.json` | Accounting class name resolution |

> **Note:** The v3 bill list API returns records under the `results` key, not `bills`. The v2 List API requires auth params as top-level form fields and query params as a JSON-encoded string under the `data` key.

---

## Getting Started

### Prerequisites
- [OpenClaw](https://openclaw.ai) installed and running
- A Bill.com account with Administrator, Accountant, or Approver role
- Your Bill.com Developer Key, API Token, and Organization ID

### Installation

1. **Clone this repo**
   ```bash
   git clone https://github.com/nicholope/billcom-agentic-approver.git
   ```

2. **Copy the skill into your OpenClaw workspace**
   ```bash
   cp -r skill ~/.openclaw/workspace/skills/billcom-agentic-approver
   ```

3. **Set up your credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your Bill.com credentials
   ```

4. **Trigger the skill**
   In any connected channel (Telegram, Discord, etc.), say:
   ```
   Check my Bill.com approval queue
   ```
   or
   ```
   Review my AP bills
   ```

---

## Example Session

See [`examples/console-demo.md`](examples/console-demo.md) for a full annotated walkthrough of a review session — including HOLD flags, notes with @mentions, and line item description enrichment.

---

## Credential Setup

| Variable | Description | Where to Find |
|---|---|---|
| `BILLCOM_DEV_KEY` | Developer API key | Bill.com → Settings → API → Developer Keys |
| `BILLCOM_USERNAME` | Login email | Your Bill.com login |
| `BILLCOM_PASSWORD` | Login password | Your Bill.com login |
| `BILLCOM_API_TOKEN` | API Sync Token | Bill.com → Settings → API → API Token |
| `BILLCOM_ORG_ID` | Organization ID | Bill.com → Settings → Account → Company |
| `BILLCOM_ENVIRONMENT` | `production` or `stage` | Choose based on target environment |

Copy `.env.example` to `.env` and fill in your values. `.env` is gitignored and must never be committed.

---

## Project Goal

This is a portfolio project demonstrating practical applications of agentic AI in accounting and finance operations.

The core thesis: **experienced judgment tasks in finance — not just data entry — can be meaningfully assisted by AI agents.** AP invoice approval is a representative example. An agent that understands vendor history, spots anomalies, enriches missing data, and routes decisions to the right human is more useful than a dashboard.

The goal is to demonstrate this model as a template for commissioned work in:
- Accounts payable automation
- Invoice review and enrichment workflows
- Agentic financial operations tooling for SMBs

If you're interested in building something similar for your team, feel free to reach out.

---

## Skill Files

```
skill/
  SKILL.md                    # Core workflow — loaded by OpenClaw at trigger time
  references/
    api-endpoints.md          # Full Bill.com v3/v2 endpoint reference
    analysis-rules.md         # AP flag definitions, thresholds, and edge cases
examples/
  console-demo.md             # Anonymized full session walkthrough
.env.example                  # Credential template
.gitignore
README.md
```

---

## License

MIT — free to use, adapt, and build on.
