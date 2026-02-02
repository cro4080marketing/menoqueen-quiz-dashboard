"""
MenoQueen Quiz — Daily Slack Snapshot

Sends a formatted daily performance report to Slack comparing
yesterday's metrics against the 7-day average.

Can be run standalone:  python slack_report.py
Or imported and called: send_daily_report()
"""

import os
import json
import re
from datetime import date, timedelta, datetime

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration (reads from env — same vars as app.py)
# ---------------------------------------------------------------------------

KLAVIYO_API_KEY = os.environ.get("KLAVIYO_API_KEY", "")
KLAVIYO_LIST_ID = os.environ.get("KLAVIYO_LIST_ID", "")
KLAVIYO_API_BASE = "https://a.klaviyo.com/api"
KLAVIYO_REVISION = "2024-02-15"

GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
GA4_CREDENTIALS_JSON = os.environ.get("GA4_CREDENTIALS_JSON", "")

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

QUIZ_STEPS_ORDER = [
    "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10", "q12",
    "email-capture", "preparing-summary",
    "result-1", "result-2", "result-3",
    "product-recommendation",
]

STEP_LABELS = {
    "q1": "Q1 - Primary Symptom",
    "q2": "Q2 - Frequency",
    "q3": "Q3 - Secondary Symptom",
    "q4": "Q4 - Intimate Health",
    "q5": "Q5 - Emotional",
    "q6": "Q6 - Impact",
    "q7": "Q7 - Diet",
    "q8": "Q8 - Supplements",
    "q9": "Q9 - Stage",
    "q10": "Q10 - Age",
    "q12": "Q12 - Relief",
    "email-capture": "Email Capture",
    "preparing-summary": "Calculating",
    "result-1": "Result 1",
    "result-2": "Result 2",
    "result-3": "Result 3",
    "product-recommendation": "Product Page",
}

QUIZ_Q_KEYS = [
    "quiz_q1", "quiz_q2", "quiz_q3", "quiz_q4", "quiz_q5",
    "quiz_q6", "quiz_q7", "quiz_q8", "quiz_q9", "quiz_q10", "quiz_q12",
]


# ---------------------------------------------------------------------------
# Data fetching (lightweight copies — no Streamlit dependency)
# ---------------------------------------------------------------------------

def _klaviyo_headers() -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {KLAVIYO_API_KEY}",
        "revision": KLAVIYO_REVISION,
        "accept": "application/json",
    }


def fetch_profiles() -> list[dict]:
    profiles: list[dict] = []
    if KLAVIYO_LIST_ID:
        url = f"{KLAVIYO_API_BASE}/lists/{KLAVIYO_LIST_ID}/profiles/"
    else:
        url = f"{KLAVIYO_API_BASE}/profiles/"
    params: dict = {"page[size]": 100}

    while url:
        resp = requests.get(url, headers=_klaviyo_headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        profiles.extend(payload.get("data", []))
        next_link = payload.get("links", {}).get("next")
        url = next_link if next_link else None
        params = {} if next_link else params

    if not KLAVIYO_LIST_ID:
        profiles = [
            p for p in profiles
            if p.get("attributes", {}).get("properties", {}).get("quiz_source") == "menoqueen_quiz"
        ]
    return profiles


def profiles_to_df(profiles: list[dict]) -> pd.DataFrame:
    rows = []
    for p in profiles:
        attrs = p.get("attributes", {})
        props = attrs.get("properties", {})
        row = {
            "email": attrs.get("email", ""),
            "created": attrs.get("created", ""),
            "quiz_completed": props.get("Quiz Completed", False),
            "current_step": props.get("quiz_current_step", ""),
        }
        for qk in QUIZ_Q_KEYS:
            row[qk] = props.get(qk, "")
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty and "created" in df.columns:
        df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True)
    return df


def filter_by_date(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or df["created"].isna().all():
        return df.iloc[0:0]
    mask = (df["created"].dt.date >= start) & (df["created"].dt.date <= end)
    return df.loc[mask]


def compute_funnel(df: pd.DataFrame) -> pd.DataFrame:
    step_index = {s: i for i, s in enumerate(QUIZ_STEPS_ORDER)}
    q_steps = [s for s in QUIZ_STEPS_ORDER if s.startswith("q")]

    def infer_rank(row):
        explicit = step_index.get(row.get("current_step", ""), -1)
        if explicit >= 0:
            return explicit
        best = -1
        for qs in q_steps:
            val = row.get(qs, "")
            if val not in ("", None):
                rank = step_index.get(qs, -1)
                if rank > best:
                    best = rank
        if row.get("email", "") and best >= 0:
            ec_rank = step_index.get("email-capture", best)
            if ec_rank > best:
                best = ec_rank
        return best

    if df.empty:
        return pd.DataFrame(columns=["step", "label", "count", "pct"])

    df = df.copy()
    df["step_rank"] = df.apply(infer_rank, axis=1)
    last_rank = len(QUIZ_STEPS_ORDER) - 1
    df.loc[df["quiz_completed"] == True, "step_rank"] = last_rank  # noqa: E712

    total = len(df)
    records = []
    for step_id in QUIZ_STEPS_ORDER:
        rank = step_index[step_id]
        reached = int((df["step_rank"] >= rank).sum())
        records.append({
            "step": step_id,
            "label": STEP_LABELS.get(step_id, step_id),
            "count": reached,
            "pct": round(reached / total * 100, 1) if total else 0,
        })
    return pd.DataFrame(records)


def fetch_shopify_orders(days_back: int = 10) -> list[dict]:
    if not (SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN):
        return []
    orders: list[dict] = []
    since = (date.today() - timedelta(days=days_back)).isoformat() + "T00:00:00Z"
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/orders.json"
    params: dict = {"status": "any", "created_at_min": since, "limit": 250}

    while url:
        resp = requests.get(
            url,
            headers={"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"},
            params=params, timeout=30,
        )
        resp.raise_for_status()
        orders.extend(resp.json().get("orders", []))
        link_header = resp.headers.get("Link", "")
        next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        if next_match:
            url = next_match.group(1)
            params = {}
        else:
            url = None
    return orders


def shopify_orders_for_date(orders: list[dict], start: date, end: date) -> list[dict]:
    filtered = []
    for o in orders:
        created = o.get("created_at", "")[:10]
        try:
            order_date = date.fromisoformat(created)
        except ValueError:
            continue
        if start <= order_date <= end:
            filtered.append(o)
    return filtered


# ---------------------------------------------------------------------------
# Build the Slack report
# ---------------------------------------------------------------------------

def _trend_emoji(current: float, average: float) -> str:
    if average == 0:
        return ""
    pct = ((current - average) / average) * 100
    if pct > 5:
        return f" :chart_with_upwards_trend: +{pct:.0f}%"
    elif pct < -5:
        return f" :chart_with_downwards_trend: {pct:.0f}%"
    else:
        return " :left_right_arrow: flat"


def _find_biggest_dropoff(funnel: pd.DataFrame) -> tuple[str, float]:
    """Find the step with the biggest percentage drop from previous step."""
    biggest_label = ""
    biggest_drop = 0.0
    prev_count = None
    for _, row in funnel.iterrows():
        count = int(row["count"])
        if prev_count is not None and prev_count > 0:
            drop_pct = round((prev_count - count) / prev_count * 100, 1)
            if drop_pct > biggest_drop:
                biggest_drop = drop_pct
                biggest_label = row["label"]
        prev_count = count
    return biggest_label, biggest_drop


def build_report_blocks() -> list[dict]:
    """Build Slack Block Kit blocks for the daily snapshot."""
    yesterday = date.today() - timedelta(days=1)
    week_start = date.today() - timedelta(days=7)
    week_end = date.today() - timedelta(days=1)

    # -- Fetch all data --
    try:
        profiles = fetch_profiles()
    except Exception as e:
        return _error_blocks(f"Klaviyo fetch failed: {e}")

    df = profiles_to_df(profiles)
    if df.empty:
        return _error_blocks("No quiz profiles found in Klaviyo.")

    # -- Filter by date ranges --
    df_yesterday = filter_by_date(df, yesterday, yesterday)
    df_week = filter_by_date(df, week_start, week_end)

    # -- Quiz Funnel metrics --
    total_yesterday = len(df_yesterday)
    completed_yesterday = int(df_yesterday["quiz_completed"].sum()) if not df_yesterday.empty else 0
    completion_rate_yesterday = round(completed_yesterday / total_yesterday * 100, 1) if total_yesterday else 0

    total_week = len(df_week)
    completed_week = int(df_week["quiz_completed"].sum()) if not df_week.empty else 0
    avg_daily_starts = round(total_week / 7, 1) if total_week else 0
    avg_daily_completions = round(completed_week / 7, 1) if completed_week else 0
    avg_completion_rate = round(completed_week / total_week * 100, 1) if total_week else 0

    # -- Emails captured --
    emails_yesterday = int(df_yesterday["email"].astype(bool).sum()) if not df_yesterday.empty else 0
    emails_week = int(df_week["email"].astype(bool).sum()) if not df_week.empty else 0
    avg_daily_emails = round(emails_week / 7, 1)

    # -- Drop-off hotspot (from all-time data for stability) --
    funnel = compute_funnel(df)
    drop_label, drop_pct = _find_biggest_dropoff(funnel)

    # -- Build Slack blocks --
    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": ":crown: MenoQueen Quiz — Daily Snapshot", "emoji": True}
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f":calendar: *Yesterday* ({yesterday.strftime('%b %d')}) vs *7-Day Avg* ({week_start.strftime('%b %d')}–{week_end.strftime('%b %d')})"}
        ]
    })

    blocks.append({"type": "divider"})

    # Quiz Funnel section
    funnel_text = (
        f":bar_chart: *QUIZ FUNNEL*\n"
        f"• *Quiz Starts:* {total_yesterday}{_trend_emoji(total_yesterday, avg_daily_starts)} _(avg: {avg_daily_starts}/day)_\n"
        f"• *Completions:* {completed_yesterday}{_trend_emoji(completed_yesterday, avg_daily_completions)} _(avg: {avg_daily_completions}/day)_\n"
        f"• *Completion Rate:* {completion_rate_yesterday}% _(avg: {avg_completion_rate}%)_\n"
        f"• *Emails Captured:* {emails_yesterday}{_trend_emoji(emails_yesterday, avg_daily_emails)} _(avg: {avg_daily_emails}/day)_"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": funnel_text}})

    # Drop-off hotspot
    if drop_label and drop_pct > 0:
        blocks.append({"type": "divider"})
        severity = ":red_circle:" if drop_pct > 40 else ":large_orange_circle:" if drop_pct > 25 else ":large_yellow_circle:"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":rotating_light: *DROP-OFF HOTSPOT*\n{severity} Biggest drop: *{drop_label}* losing *{drop_pct}%* of users"}
        })

    # Shopify section (optional)
    try:
        all_orders = fetch_shopify_orders(days_back=10)
        if all_orders:
            orders_yesterday = shopify_orders_for_date(all_orders, yesterday, yesterday)
            orders_week = shopify_orders_for_date(all_orders, week_start, week_end)

            rev_yesterday = sum(float(o.get("total_price", 0)) for o in orders_yesterday)
            rev_week = sum(float(o.get("total_price", 0)) for o in orders_week)
            avg_daily_orders = round(len(orders_week) / 7, 1)
            avg_daily_rev = round(rev_week / 7, 2)

            blocks.append({"type": "divider"})
            shopify_text = (
                f":shopping_trolley: *SHOPIFY*\n"
                f"• *Orders:* {len(orders_yesterday)}{_trend_emoji(len(orders_yesterday), avg_daily_orders)} _(avg: {avg_daily_orders}/day)_\n"
                f"• *Revenue:* ${rev_yesterday:,.2f}{_trend_emoji(rev_yesterday, avg_daily_rev)} _(avg: ${avg_daily_rev:,.2f}/day)_"
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": shopify_text}})
    except Exception:
        pass  # Shopify is optional — skip silently

    # Footer with link
    blocks.append({"type": "divider"})
    footer_text = ":sparkles: _Sent automatically by MenoQueen Quiz Analytics_"
    if DASHBOARD_URL:
        footer_text += f"  |  <{DASHBOARD_URL}|View Full Dashboard>"
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": footer_text}]
    })

    return blocks


def _error_blocks(msg: str) -> list[dict]:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":crown: MenoQueen Quiz — Daily Snapshot", "emoji": True}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":warning: *Report failed:* {msg}"}
        },
    ]


# ---------------------------------------------------------------------------
# Send to Slack
# ---------------------------------------------------------------------------

def send_daily_report() -> bool:
    """Build and send the daily snapshot to Slack. Returns True on success."""
    if not SLACK_WEBHOOK_URL:
        print("[slack_report] SLACK_WEBHOOK_URL not set — skipping.")
        return False

    blocks = build_report_blocks()
    payload = {
        "text": "MenoQueen Quiz — Daily Snapshot",  # Fallback for notifications
        "blocks": blocks,
    }

    resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    if resp.status_code == 200 and resp.text == "ok":
        print(f"[slack_report] Sent daily report at {datetime.now().isoformat()}")
        return True
    else:
        print(f"[slack_report] Failed: {resp.status_code} — {resp.text}")
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Re-read env vars after dotenv
    KLAVIYO_API_KEY = os.environ.get("KLAVIYO_API_KEY", "")
    KLAVIYO_LIST_ID = os.environ.get("KLAVIYO_LIST_ID", "")
    GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
    GA4_CREDENTIALS_JSON = os.environ.get("GA4_CREDENTIALS_JSON", "")
    SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
    SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
    DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

    ok = send_daily_report()
    exit(0 if ok else 1)
