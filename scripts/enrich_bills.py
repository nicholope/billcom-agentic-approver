#!/usr/bin/env python3
"""
enrich_bills.py — Bill.com AP Enrichment Script
================================================
Authenticates, fetches the 20 most recent ASSIGNED bills, enriches each with
full bill details, vendor profile, and payment history, applies AP analysis
flags, and writes results to a JSON file for use by the review session.

Usage:
    python3 scripts/enrich_bills.py [--output /path/to/output.json] [--max N]

Credentials are loaded from a .env file in the project root (one directory
above this script), or from environment variables already set in the shell.
Copy .env.example to .env and fill in your values before running.

Required env vars:
    BILLCOM_DEV_KEY       — Developer API key
    BILLCOM_USERNAME      — Bill.com login username
    BILLCOM_API_TOKEN     — API token (used as password for programmatic login)
    BILLCOM_ORG_ID        — Organization ID
    BILLCOM_ENVIRONMENT   — "production" or "stage"

Output:
    JSON array of enriched bill objects, one per pending bill.
    Default: /tmp/billcom_enriched.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Load .env from project root (parent of scripts/) if present.
# Falls back to env vars already set in the shell.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    # python-dotenv not installed; rely on shell env vars.
    # Install with: pip install python-dotenv
    pass

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URLS = {
    "production": "https://gateway.prod.bill.com/connect",
    "stage": "https://gateway.stage.bill.com/connect",
}

DEFAULT_OUTPUT = "/tmp/billcom_enriched.json"
DEFAULT_MAX = 20


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _curl_get(url, sid, dev_key):
    result = subprocess.run(
        ["curl", "-s", url,
         "-H", f"sessionId: {sid}",
         "-H", f"devKey: {dev_key}"],
        capture_output=True, text=True, timeout=20
    )
    return json.loads(result.stdout)


def _v2_list(entity, sid, dev_key):
    result = subprocess.run(
        ["curl", "-s", "-X", "POST",
         f"https://api.bill.com/api/v2/List/{entity}.json",
         "--data-urlencode", f"devKey={dev_key}",
         "--data-urlencode", f"sessionId={sid}",
         "--data-urlencode", 'data={"start":0,"max":999}'],
        capture_output=True, text=True, timeout=20
    )
    return json.loads(result.stdout).get("response_data", [])


def login(base_url, username, api_token, org_id, dev_key):
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{base_url}/v3/login",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({
             "username": username,
             "password": api_token,
             "organizationId": org_id,
             "devKey": dev_key,
         })],
        capture_output=True, text=True, timeout=20
    )
    resp = json.loads(result.stdout)
    sid = resp.get("sessionId")
    if not sid:
        print(f"Login failed: {resp}", file=sys.stderr)
        sys.exit(1)
    return sid


# ---------------------------------------------------------------------------
# Analysis flags
# ---------------------------------------------------------------------------

def analyze(bill_data, vendor, hist, today):
    """Return (flags, severity). flags = list of (level, name, message)."""
    amount = float(bill_data.get("amount") or 0)
    hist_amounts = [float(b.get("amount") or 0) for b in hist]
    count = len(hist_amounts)
    avg = sum(hist_amounts) / count if count else 0
    max_ever = max(hist_amounts) if hist_amounts else 0
    t6 = hist_amounts[:6]
    trailing6avg = sum(t6) / len(t6) if t6 else 0
    last7d_count = sum(
        1 for b in hist
        if (b.get("createdTime") or "")[:10] >= str(today.replace(day=max(1, today.day - 7)))
    )

    inv = bill_data.get("invoice") or {}
    inv_num = inv.get("invoiceNumber")
    inv_date = inv.get("invoiceDate")
    due_date = bill_data.get("dueDate")
    hist_inv_nums = [
        b.get("invoice", {}).get("invoiceNumber")
        for b in hist
        if (b.get("invoice") or {}).get("invoiceNumber")
    ]

    flags = []
    hold = False

    # DUPLICATE_INVOICE
    if inv_num and inv_num in hist_inv_nums:
        dupe = next((b for b in hist if (b.get("invoice") or {}).get("invoiceNumber") == inv_num), None)
        dupe_date = (dupe.get("createdTime") or "")[:10] if dupe else "?"
        flags.append(("HOLD", "DUPLICATE_INVOICE",
                       f"Invoice #{inv_num} already on file from {dupe_date}. Possible duplicate."))
        hold = True

    # EXTREME_AMOUNT_SPIKE (>200% of trailing avg)
    if count >= 3 and trailing6avg > 0 and amount > trailing6avg * 2.0:
        pct = int((amount / trailing6avg - 1) * 100)
        flags.append(("HOLD", "EXTREME_AMOUNT_SPIKE",
                       f"Amount is {pct}% above trailing avg of ${trailing6avg:,.2f}. Unusually high."))
        hold = True

    # THIN_HISTORY
    if 3 <= count <= 9:
        flags.append(("REVIEW", "THIN_HISTORY",
                       f"Only {count} prior bill(s) on record. Small sample — apply extra scrutiny."))

    # AMOUNT_SPIKE (>125%, skip if EXTREME already fired)
    if (count >= 3 and trailing6avg > 0 and amount > trailing6avg * 1.25
            and not any(f[1] == "EXTREME_AMOUNT_SPIKE" for f in flags)):
        pct = int((amount / trailing6avg - 1) * 100)
        flags.append(("REVIEW", "AMOUNT_SPIKE",
                       f"Amount is {pct}% above trailing avg of ${trailing6avg:,.2f}."))

    # ALL_TIME_HIGH
    if count >= 1 and amount > max_ever:
        flags.append(("REVIEW", "ALL_TIME_HIGH",
                       f"Highest ever from this vendor. Previous max: ${max_ever:,.2f}."))

    # MISSING_INVOICE_NUMBER
    if not inv_num:
        flags.append(("REVIEW", "MISSING_INVOICE_NUMBER",
                       "No invoice number. Required for record-keeping and duplicate detection."))

    # MISSING_INVOICE_DATE
    if not inv_date:
        flags.append(("REVIEW", "MISSING_INVOICE_DATE", "No invoice date provided."))

    # PAST_DUE
    if due_date and due_date < str(today):
        flags.append(("REVIEW", "PAST_DUE",
                       f"Due date {due_date} has already passed."))

    # RUSHED_DUE_DATE
    if due_date and due_date >= str(today):
        due_dt = date.fromisoformat(due_date)
        days_out = (due_dt - today).days
        if days_out <= 3:
            flags.append(("REVIEW", "RUSHED_DUE_DATE",
                           f"Due in {days_out} day(s). Tight window — confirm urgency."))

    # NEW_VENDOR
    if count < 3:
        flags.append(("REVIEW", "NEW_VENDOR",
                       f"Only {count} prior bill(s) on file. Verify vendor legitimacy."))

    # VAGUE_LINE_ITEMS
    for i, li in enumerate(bill_data.get("billLineItems") or [], 1):
        desc = (li.get("description") or "").strip()
        if len(desc) < 5:
            flags.append(("REVIEW", "VAGUE_LINE_ITEMS",
                           f"Line item #{i} has no or insufficient description."))
            break

    # ROUND_NUMBER (>= $500, skip if < $50 trailing avg)
    if (amount >= 500 and amount == int(amount)
            and (int(amount) % 100 == 0 or int(amount) % 500 == 0 or int(amount) % 1000 == 0)):
        flags.append(("REVIEW", "ROUND_NUMBER",
                       "Round number. May be normal for retainer/subscription billing — verify."))

    # FREQUENCY_SPIKE
    if last7d_count >= 2:
        flags.append(("REVIEW", "FREQUENCY_SPIKE",
                       f"{last7d_count} other bill(s) from this vendor in the last 7 days."))

    severity = "HOLD" if hold else ("REVIEW" if flags else "CLEAN")
    return flags, severity


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------

def enrich(max_bills=DEFAULT_MAX, output_path=DEFAULT_OUTPUT):
    # Load credentials from env
    dev_key = os.environ.get("BILLCOM_DEV_KEY", "")
    username = os.environ.get("BILLCOM_USERNAME", "")
    api_token = os.environ.get("BILLCOM_API_TOKEN", "")
    org_id = os.environ.get("BILLCOM_ORG_ID", "")
    environment = os.environ.get("BILLCOM_ENVIRONMENT", "production")

    missing = [k for k, v in {
        "BILLCOM_DEV_KEY": dev_key,
        "BILLCOM_USERNAME": username,
        "BILLCOM_API_TOKEN": api_token,
        "BILLCOM_ORG_ID": org_id,
    }.items() if not v]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        print("Load them with: source ~/Projects/billcom-ap-priority/.env", file=sys.stderr)
        sys.exit(1)

    base_url = BASE_URLS.get(environment, BASE_URLS["production"])
    print(f"Environment: {environment} ({base_url})", file=sys.stderr)

    # Authenticate
    print("Authenticating...", file=sys.stderr)
    sid = login(base_url, username, api_token, org_id, dev_key)
    print("  ✓ Session established", file=sys.stderr)

    def get(path):
        return _curl_get(base_url + path, sid, dev_key)

    # Build GL and class lookup maps (once per session)
    print("Loading COA and class maps...", file=sys.stderr)
    coa_map = {i["id"]: i["name"] for i in _v2_list("ChartOfAccount", sid, dev_key)}
    cls_map = {i["id"]: i["name"] for i in _v2_list("ActgClass", sid, dev_key)}
    print(f"  ✓ COA: {len(coa_map)} entries, Classes: {len(cls_map)} entries", file=sys.stderr)

    # Fetch pending queue
    # Note: /v3/bill-approvals/pending-user-approvals is broken with API token auth.
    # Workaround: filter bills by approvalStatus=ASSIGNED, newest first.
    print(f"Fetching up to {max_bills} pending bills...", file=sys.stderr)
    resp = get(f"/v3/bills?filters=approvalStatus:eq:ASSIGNED&sort=createdTime:desc&max={max_bills}")
    bills = resp.get("results", [])
    print(f"  ✓ Found {len(bills)} pending bill(s)", file=sys.stderr)

    if not bills:
        print("No bills pending approval.", file=sys.stderr)
        return []

    today = date.today()
    vendor_cache = {}
    history_cache = {}
    enriched = []

    for idx, bill in enumerate(bills, 1):
        bill_id = bill["id"]
        vendor_id = bill["vendorId"]
        vendor_name = bill.get("vendorName", "Unknown")
        amount = float(bill.get("amount") or 0)
        print(f"  [{idx}/{len(bills)}] {vendor_name} ${amount:,.2f}...", file=sys.stderr)

        # Full bill details
        bd = get(f"/v3/bills/{bill_id}?billApprovals=true")
        if isinstance(bd, list):
            bd = bill  # fallback to list-level data on error

        # Vendor (cached per vendor_id)
        if vendor_id not in vendor_cache:
            vd = get(f"/v3/vendors/{vendor_id}")
            vendor_cache[vendor_id] = vd if isinstance(vd, dict) else {}
        vendor = vendor_cache[vendor_id]

        # History: last 20 bills from this vendor, excluding current bill (cached)
        if vendor_id not in history_cache:
            hd = get(f"/v3/bills?filters=vendorId:eq:{vendor_id}&sort=createdTime:desc&max=21")
            hist = [b for b in hd.get("results", []) if b["id"] != bill_id][:20]
            history_cache[vendor_id] = hist
        hist = history_cache[vendor_id]

        # Run analysis
        flags, severity = analyze(bd, vendor, hist, today)

        # Resolve line item GL/class names
        line_items = []
        for li in (bd.get("billLineItems") or []):
            cls = li.get("classifications") or {}
            line_items.append({
                "id": li.get("id"),
                "amount": float(li.get("amount") or 0),
                "description": li.get("description") or "",
                "gl_id": cls.get("chartOfAccountId"),
                "gl_name": coa_map.get(cls.get("chartOfAccountId"), "—"),
                "class_id": cls.get("accountingClassId"),
                "class_name": cls_map.get(cls.get("accountingClassId"), "—"),
            })

        # Build history summary
        hist_amounts = [float(b.get("amount") or 0) for b in hist]
        count = len(hist_amounts)
        last_bill = hist[0] if hist else None
        history_summary = {
            "count": count,
            "avg": round(sum(hist_amounts) / count, 2) if count else 0,
            "max": round(max(hist_amounts), 2) if hist_amounts else 0,
            "trailing6avg": round(sum(hist_amounts[:6]) / min(count, 6), 2) if count else 0,
            "last_date": (last_bill.get("createdTime") or "")[:10] if last_bill else None,
            "last_amount": float(last_bill.get("amount") or 0) if last_bill else None,
        }

        inv = bd.get("invoice") or {}
        enriched.append({
            "bill_id": bill_id,
            "vendor_id": vendor_id,
            "vendor_name": vendor.get("name", vendor_name),
            "amount": float(bd.get("amount") or 0),
            "inv_num": inv.get("invoiceNumber"),
            "inv_date": inv.get("invoiceDate"),
            "due_date": bd.get("dueDate"),
            "created": (bd.get("createdTime") or "")[:10],
            "description": bd.get("description") or "",
            "payment_status": bd.get("paymentStatus"),
            "approval_status": bd.get("approvalStatus"),
            "line_items": line_items,
            "history": history_summary,
            "flags": flags,
            "severity": severity,
        })

        icon = {"HOLD": "🔴", "REVIEW": "🟡", "CLEAN": "🟢"}.get(severity, "?")
        print(f"     {icon} {severity} ({len(flags)} flag(s))", file=sys.stderr)

    # Summary
    holds = sum(1 for b in enriched if b["severity"] == "HOLD")
    reviews = sum(1 for b in enriched if b["severity"] == "REVIEW")
    cleans = sum(1 for b in enriched if b["severity"] == "CLEAN")
    print(f"\nDone: {len(enriched)} bills — 🔴 {holds} HOLD · 🟡 {reviews} REVIEW · 🟢 {cleans} CLEAN",
          file=sys.stderr)

    with open(output_path, "w") as f:
        json.dump(enriched, f, default=str, indent=2)
    print(f"Output saved to: {output_path}", file=sys.stderr)

    return enriched


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich Bill.com AP queue for review.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX, help="Max bills to fetch (default 20)")
    args = parser.parse_args()
    enrich(max_bills=args.max, output_path=args.output)
