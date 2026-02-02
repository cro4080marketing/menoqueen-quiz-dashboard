import os
import json
import re
from datetime import date, timedelta
from collections import Counter
from urllib.parse import urlparse, parse_qs

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MenoQueen Quiz Analytics",
    page_icon="\U0001f451",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Klaviyo
KLAVIYO_API_KEY = os.environ.get("KLAVIYO_API_KEY", "")
KLAVIYO_LIST_ID = os.environ.get("KLAVIYO_LIST_ID", "")
KLAVIYO_API_BASE = "https://a.klaviyo.com/api"
KLAVIYO_REVISION = "2024-02-15"

# Anthropic (Claude AI insights)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Google Analytics 4
GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
GA4_CREDENTIALS_JSON = os.environ.get("GA4_CREDENTIALS_JSON", "")

# Shopify
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

# ---------------------------------------------------------------------------
# Quiz metadata
# ---------------------------------------------------------------------------

QUESTION_LABELS = {
    "quiz_q1": "Primary Symptom",
    "quiz_q2": "Symptom Frequency",
    "quiz_q3": "Secondary Symptom",
    "quiz_q4": "Intimate Health",
    "quiz_q5": "Emotional Health",
    "quiz_q6": "Biggest Impact",
    "quiz_q7": "Diet",
    "quiz_q8": "Supplements",
    "quiz_q9": "Menopause Stage",
    "quiz_q10": "Age Range",
    "quiz_q12": "Relief Status",
}

QUIZ_Q_KEYS = list(QUESTION_LABELS.keys())

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

# Question groupings for the Responses page
Q_HEALTH = ["quiz_q1", "quiz_q2", "quiz_q3", "quiz_q4", "quiz_q5"]
Q_LIFESTYLE = ["quiz_q6", "quiz_q7", "quiz_q8"]
Q_DEMOGRAPHICS = ["quiz_q9", "quiz_q10", "quiz_q12"]


def _pretty(value: str) -> str:
    import re as _re
    # Detect age-range patterns like "55_64", "65_69", "70_plus"
    m = _re.match(r"^(\d{2})_(\d{2})$", value)
    if m:
        return f"{m.group(1)}–{m.group(2)}"
    m = _re.match(r"^(\d{2})_plus$", value, _re.IGNORECASE)
    if m:
        return f"{m.group(1)}+"
    m = _re.match(r"^under_(\d{2})$", value, _re.IGNORECASE)
    if m:
        return f"Under {m.group(1)}"
    return value.replace("_", " ").replace("-", " ").title()


# =========================================================================
#  DATA SOURCES
# =========================================================================

# ---------------------------------------------------------------------------
# 1. Klaviyo
# ---------------------------------------------------------------------------

def _klaviyo_headers() -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {KLAVIYO_API_KEY}",
        "revision": KLAVIYO_REVISION,
        "accept": "application/json",
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_quiz_profiles() -> list[dict]:
    """Fetch quiz profiles from Klaviyo (paginated)."""
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


def profiles_to_dataframe(profiles: list[dict]) -> pd.DataFrame:
    rows = []
    for p in profiles:
        attrs = p.get("attributes", {})
        props = attrs.get("properties", {})
        row = {
            "email": attrs.get("email", ""),
            "created": attrs.get("created", ""),
            "quiz_completed": props.get("Quiz Completed", False),
            "quiz_completed_at": props.get("quiz_completed_at", ""),
            "current_step": props.get("quiz_current_step", ""),
        }
        for qk in QUIZ_Q_KEYS:
            row[qk] = props.get(qk, "")
        rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty and "created" in df.columns:
        df["created"] = pd.to_datetime(df["created"], errors="coerce", utc=True)
    return df


# ---------------------------------------------------------------------------
# 2. Google Analytics 4
# ---------------------------------------------------------------------------

def _ga4_available() -> bool:
    return bool(GA4_PROPERTY_ID and GA4_CREDENTIALS_JSON)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ga4_step_pageviews(start_date: str = "30daysAgo", end_date: str = "today") -> dict:
    """Query GA4 for pageviews per quiz step."""
    from google.oauth2 import service_account
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest,
    )

    creds = service_account.Credentials.from_service_account_info(
        json.loads(GA4_CREDENTIALS_JSON)
    )
    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePathPlusQueryString")],
        metrics=[Metric(name="screenPageViews")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    value="/pages/quiz-1",
                ),
            )
        ),
    )
    response = client.run_report(request)

    step_counts: dict[str, int] = {}
    for row in response.rows:
        url_path = row.dimension_values[0].value
        views = int(row.metric_values[0].value)
        match = re.search(r"[?&]step=([^&]+)", url_path)
        if match:
            step = match.group(1)
        else:
            step = "q1"
        step_counts[step] = step_counts.get(step, 0) + views

    return step_counts


# ---------------------------------------------------------------------------
# 3. Shopify
# ---------------------------------------------------------------------------

def _shopify_available() -> bool:
    return bool(SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN)


def _shopify_headers() -> dict:
    return {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_shopify_orders(days_back: int = 60) -> list[dict]:
    """Fetch recent Shopify orders (paginated via Link header)."""
    orders: list[dict] = []
    since = (date.today() - timedelta(days=days_back)).isoformat() + "T00:00:00Z"
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/orders.json"
    params: dict = {
        "status": "any",
        "created_at_min": since,
        "limit": 250,
    }

    while url:
        resp = requests.get(url, headers=_shopify_headers(), params=params, timeout=30)
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


def compute_shopify_metrics(orders: list[dict]) -> dict:
    """Compute summary metrics from a list of Shopify orders."""
    total = len(orders)
    revenue = sum(float(o.get("total_price", 0)) for o in orders)

    subscription = 0
    onetime = 0
    coupon_counts: dict[str, int] = {}

    for o in orders:
        is_sub = any(
            item.get("selling_plan_allocation")
            for item in o.get("line_items", [])
        )
        if is_sub:
            subscription += 1
        else:
            onetime += 1

        for dc in o.get("discount_codes", []):
            code = dc.get("code", "").upper()
            coupon_counts[code] = coupon_counts.get(code, 0) + 1

    return {
        "total_orders": total,
        "revenue": revenue,
        "subscription": subscription,
        "onetime": onetime,
        "sub_pct": round(subscription / total * 100, 1) if total else 0,
        "coupon_counts": coupon_counts,
    }


# =========================================================================
#  METRIC HELPERS
# =========================================================================

def compute_answer_distribution(df: pd.DataFrame, col: str) -> pd.DataFrame:
    vals = df[col].dropna().astype(str)
    vals = vals[vals != ""]
    items: list[str] = []
    for v in vals:
        for part in v.split(","):
            part = part.strip()
            if part:
                items.append(_pretty(part))
    counts = Counter(items)
    out = pd.DataFrame(counts.items(), columns=["answer", "count"])
    return out.sort_values("count", ascending=False).reset_index(drop=True)


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


# =========================================================================
#  AI INSIGHTS (Claude via Anthropic API)
# =========================================================================

def _filter_by_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or df["created"].isna().all():
        return df
    mask = (df["created"].dt.date >= start) & (df["created"].dt.date <= end)
    return df.loc[mask]


def _ga4_summary_block(ga4_steps: dict) -> str:
    lines = ["", "Google Analytics Funnel (pageviews per step):"]
    prev = None
    for step_id in QUIZ_STEPS_ORDER:
        views = ga4_steps.get(step_id, 0)
        if views == 0:
            continue
        drop = ""
        if prev is not None and prev > 0:
            lost = prev - views
            drop = f"  (lost {lost}, -{round(lost/prev*100,1)}%)"
        lines.append(f"  {STEP_LABELS.get(step_id, step_id)}: {views}{drop}")
        prev = views
    return "\n".join(lines)


def _shopify_summary_block(metrics: dict) -> str:
    lines = [
        "",
        "Shopify Revenue:",
        f"  Total orders: {metrics['total_orders']}",
        f"  Revenue: ${metrics['revenue']:,.2f}",
        f"  Subscription orders: {metrics['subscription']} ({metrics['sub_pct']}%)",
        f"  One-time orders: {metrics['onetime']}",
    ]
    for code, count in metrics.get("coupon_counts", {}).items():
        lines.append(f"  Coupon {code}: {count} orders")
    return "\n".join(lines)


def build_data_summary(
    df: pd.DataFrame,
    label: str = "",
    ga4_steps: dict | None = None,
    shopify_metrics: dict | None = None,
) -> str:
    total = len(df)
    emails = int((df["email"] != "").sum()) if not df.empty else 0
    completed = int(df["quiz_completed"].sum()) if not df.empty else 0

    header = f"=== {label} ===" if label else "=== MenoQueen Quiz Data Snapshot ==="
    lines = [
        header,
        f"Total profiles: {total}",
        f"Emails captured: {emails} ({round(emails/total*100,1) if total else 0}%)",
        f"Completed: {completed} ({round(completed/total*100,1) if total else 0}%)",
        "",
    ]

    if ga4_steps:
        lines.append(_ga4_summary_block(ga4_steps))
        lines.append("")

    funnel = compute_funnel(df)
    if not funnel.empty:
        lines.append("Klaviyo Funnel (step | count | drop-off from previous):")
        prev = None
        for _, row in funnel.iterrows():
            drop = ""
            if prev is not None and prev > 0:
                lost = prev - row["count"]
                drop = f"  (lost {lost}, -{round(lost/prev*100,1)}%)"
            lines.append(f"  {row['label']}: {row['count']}{drop}")
            prev = row["count"]
        lines.append("")

    if shopify_metrics:
        lines.append(_shopify_summary_block(shopify_metrics))
        lines.append("")

    lines.append("Answer Distributions:")
    for qk in QUIZ_Q_KEYS:
        qlabel = QUESTION_LABELS.get(qk, qk)
        dist = compute_answer_distribution(df, qk)
        if dist.empty:
            continue
        lines.append(f"\n  {qlabel} ({qk}):")
        for _, r in dist.iterrows():
            pct = round(r["count"] / total * 100, 1) if total else 0
            lines.append(f"    {r['answer']}: {r['count']} ({pct}%)")

    return "\n".join(lines)


def build_comparison_summary(
    df: pd.DataFrame,
    start_a: date, end_a: date,
    start_b: date, end_b: date,
    ga4_steps_a: dict | None = None,
    ga4_steps_b: dict | None = None,
    shopify_metrics_a: dict | None = None,
    shopify_metrics_b: dict | None = None,
) -> str:
    df_a = _filter_by_dates(df, start_a, end_a)
    df_b = _filter_by_dates(df, start_b, end_b)
    label_a = f"PERIOD A: {start_a.strftime('%b %d')} \u2013 {end_a.strftime('%b %d, %Y')} ({len(df_a)} profiles)"
    label_b = f"PERIOD B: {start_b.strftime('%b %d')} \u2013 {end_b.strftime('%b %d, %Y')} ({len(df_b)} profiles)"
    summary_a = build_data_summary(df_a, label_a, ga4_steps=ga4_steps_a, shopify_metrics=shopify_metrics_a)
    summary_b = build_data_summary(df_b, label_b, ga4_steps=ga4_steps_b, shopify_metrics=shopify_metrics_b)
    return summary_a + "\n\n" + summary_b


def get_claude_insights(summary: str, mode: str = "snapshot", custom_question: str = "") -> str:
    system_prompt = (
        "You are a quiz funnel conversion analyst for MenoQueen, a menopause "
        "supplement brand. You have access to data from three sources: "
        "Google Analytics (anonymous pageviews per step), Klaviyo (post-email "
        "quiz profiles and answer data), and Shopify (orders and revenue). "
        "Be specific, reference actual numbers from the data, and "
        "prioritize recommendations by potential revenue impact. Keep your analysis "
        "concise. Format with markdown headers (##) and bullet points."
    )

    if mode == "comparison":
        user_content = (
            "Compare these two time periods of quiz funnel data.\n"
            "Period A is the BASELINE (the earlier / 'good' period).\n"
            "Period B is the RECENT period (the one the client is concerned about).\n\n"
            "Identify:\n"
            "1. Key metric changes between the periods\n"
            "2. Which funnel steps got worse (or better) and by how much\n"
            "3. Any shifts in answer distributions that could explain behaviour changes\n"
            "4. Revenue impact\n"
            "5. 3-5 specific, prioritised recommendations to fix any declines\n\n"
        )
    else:
        user_content = (
            "Analyze this quiz funnel data. Identify:\n"
            "1. The biggest drop-off points and likely causes\n"
            "2. Patterns in who completes vs. who drops off\n"
            "3. What the symptom/answer distributions reveal about the audience\n"
            "4. Revenue insights from Shopify (if available)\n"
            "5. 3-5 specific, actionable recommendations to improve conversion\n\n"
        )

    if custom_question:
        user_content += f'The client specifically wants to know: "{custom_question}"\n\n'

    user_content += summary

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2500,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    blocks = data.get("content", [])
    return blocks[0]["text"] if blocks else "No response received."


def _run_analysis(summary: str, mode: str, custom_question: str):
    try:
        insights = get_claude_insights(summary, mode=mode, custom_question=custom_question)
        st.session_state["ai_insights"] = insights
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        if status == 401:
            st.error("Invalid Anthropic API key. Check your ANTHROPIC_API_KEY.")
        elif status == 429:
            st.error("Rate limited by Anthropic API. Wait a moment and try again.")
        else:
            st.error(f"Anthropic API error: {status}")
    except requests.exceptions.Timeout:
        st.error("Claude API request timed out. Try again.")
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")


# =========================================================================
#  V2 DESIGN SYSTEM
# =========================================================================

# -- Color constants --
CLR_KLAVIYO = "#7C3AED"
CLR_GA4 = "#F59E0B"
CLR_SHOPIFY = "#10B981"
CLR_AI = "#3B82F6"
CLR_GOOD = "#10B981"
CLR_WARN = "#F59E0B"
CLR_DANGER = "#EF4444"
CLR_CRITICAL = "#DC2626"
CLR_BG_CARD = "#1A1D24"
CLR_TEXT = "#F9FAFB"
CLR_TEXT_SEC = "#9CA3AF"
CLR_TEXT_MUTED = "#6B7280"
CLR_BORDER = "#2D3039"

CHART_COLORS = ["#7C3AED", "#A78BFA", "#C4B5FD", "#8B5CF6", "#6D28D9", "#5B21B6", "#4C1D95"]
CHART_MULTI = ["#7C3AED", "#F59E0B", "#10B981", "#3B82F6", "#EF4444", "#A78BFA", "#34D399"]


def inject_css():
    st.markdown("""
    <style>
    /* ---- Google Font ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ---- Global ---- */
    .stApp { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }

    /* ---- Sidebar styling ---- */
    section[data-testid="stSidebar"] {
        background-color: #0E1117;
        border-right: 1px solid #2D3039;
    }
    section[data-testid="stSidebar"] .stRadio > label { display: none; }
    section[data-testid="stSidebar"] .stRadio > div {
        gap: 2px;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        background: transparent;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 0;
        font-size: 0.9rem;
        font-weight: 500;
        color: #9CA3AF;
        cursor: pointer;
        transition: all 0.15s ease;
        border-left: 3px solid transparent;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: #252830;
        color: #F9FAFB;
    }
    section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"],
    section[data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
        background: rgba(124, 58, 237, 0.1);
        color: #F9FAFB;
        border-left: 3px solid #7C3AED;
        font-weight: 600;
    }

    /* ---- Metric Card ---- */
    .metric-card {
        background: #1A1D24;
        border: 1px solid #2D3039;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        transition: all 0.2s ease;
        margin-bottom: 12px;
    }
    .metric-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }
    .metric-card--klaviyo { border-left: 4px solid #7C3AED; }
    .metric-card--ga4 { border-left: 4px solid #F59E0B; }
    .metric-card--shopify { border-left: 4px solid #10B981; }
    .metric-card--ai { border-left: 4px solid #3B82F6; }

    .metric-card .metric-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .metric-card .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #F9FAFB;
        line-height: 1.2;
    }
    .metric-card .metric-sub {
        font-size: 0.8rem;
        color: #9CA3AF;
        margin-top: 4px;
    }

    /* ---- Step Cards (Drop-off Report) ---- */
    .step-card {
        background: #1A1D24;
        border: 1px solid #2D3039;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 4px;
        position: relative;
    }
    .step-card--good { border-left: 4px solid #10B981; }
    .step-card--warn {
        border-left: 4px solid #F59E0B;
        background: rgba(245, 158, 11, 0.03);
    }
    .step-card--danger {
        border-left: 4px solid #EF4444;
        background: rgba(239, 68, 68, 0.04);
    }
    .step-card--critical {
        border-left: 4px solid #DC2626;
        background: rgba(220, 38, 38, 0.06);
        box-shadow: 0 0 8px rgba(220, 38, 38, 0.15);
    }
    .step-card .step-name {
        font-size: 0.95rem;
        font-weight: 600;
        color: #F9FAFB;
    }
    .step-card .step-counts {
        font-size: 0.8rem;
        color: #9CA3AF;
        margin-top: 4px;
    }
    .step-card .step-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-left: 8px;
    }
    .badge-attention {
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
    }
    .badge-critical {
        background: rgba(220, 38, 38, 0.2);
        color: #DC2626;
        animation: pulse-badge 2s ease-in-out infinite;
    }
    @keyframes pulse-badge {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* ---- Connector Arrow ---- */
    .step-connector {
        text-align: center;
        padding: 2px 0;
        font-size: 0.78rem;
        font-weight: 600;
        color: #6B7280;
    }
    .step-connector--warn { color: #F59E0B; }
    .step-connector--danger { color: #EF4444; }
    .step-connector--critical { color: #DC2626; }

    /* ---- Attention Banner ---- */
    .attention-banner {
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .attention-banner--warn {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.2);
    }
    .attention-banner--danger {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.2);
    }
    .attention-banner .banner-icon { font-size: 1.4rem; }
    .attention-banner .banner-text {
        font-size: 0.9rem;
        color: #F9FAFB;
    }
    .attention-banner .banner-text strong { font-weight: 700; }

    /* ---- Source Badge ---- */
    .source-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .source-badge--klaviyo { background: rgba(124,58,237,0.15); color: #A78BFA; }
    .source-badge--ga4 { background: rgba(245,158,11,0.15); color: #F59E0B; }
    .source-badge--shopify { background: rgba(16,185,129,0.15); color: #10B981; }
    .source-badge--ai { background: rgba(59,130,246,0.15); color: #3B82F6; }

    /* ---- Status Dot ---- */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    .status-dot--connected { background: #10B981; }
    .status-dot--disconnected { background: #4B5563; }

    /* ---- Progress Bar (mini funnel) ---- */
    .mini-funnel-bar {
        background: #252830;
        border-radius: 6px;
        height: 28px;
        margin-bottom: 8px;
        overflow: hidden;
        position: relative;
    }
    .mini-funnel-fill {
        height: 100%;
        border-radius: 6px;
        display: flex;
        align-items: center;
        padding-left: 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #FFF;
        transition: width 0.5s ease;
    }
    .mini-funnel-label {
        font-size: 0.8rem;
        color: #9CA3AF;
        display: flex;
        justify-content: space-between;
        margin-bottom: 2px;
    }

    /* ---- Chart Container ---- */
    .chart-container {
        background: #1A1D24;
        border: 1px solid #2D3039;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .chart-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 12px;
    }

    /* ---- Attribution Flow ---- */
    .attribution-row {
        background: #1A1D24;
        border: 1px solid #2D3039;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .attribution-row .attr-label {
        font-size: 0.85rem;
        color: #9CA3AF;
    }
    .attribution-row .attr-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #F9FAFB;
    }
    .attribution-row .attr-pct {
        font-size: 0.8rem;
        color: #10B981;
        font-weight: 600;
    }
    .attribution-arrow {
        text-align: center;
        color: #4B5563;
        font-size: 1.2rem;
        margin: 2px 0;
    }

    /* ---- Section header ---- */
    .section-header {
        font-size: 0.7rem;
        font-weight: 700;
        color: #4B5563;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 16px 0 4px 16px;
    }

    /* ---- Page title ---- */
    .page-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F9FAFB;
        margin-bottom: 4px;
    }
    .page-subtitle {
        font-size: 0.85rem;
        color: #6B7280;
        margin-bottom: 20px;
    }

    /* ---- Tab styling ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        background: #1A1D24;
        border-radius: 10px;
        padding: 4px;
        border: 1px solid #2D3039;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
        color: #9CA3AF;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(124, 58, 237, 0.15);
        color: #F9FAFB;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)


def metric_card(label: str, value: str, subtitle: str = "", source: str = "klaviyo") -> str:
    """Return HTML for a styled metric card."""
    return f"""
    <div class="metric-card metric-card--{source}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {'<div class="metric-sub">' + subtitle + '</div>' if subtitle else ''}
    </div>
    """


def apply_chart_theme(fig):
    """Apply dark theme to any Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=CLR_TEXT, family="Inter, sans-serif", size=12),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
        margin=dict(l=20, r=20, t=10, b=10),
        legend=dict(font=dict(color=CLR_TEXT_SEC)),
    )
    return fig


def get_severity(drop_pct: float) -> str:
    if drop_pct < 10:
        return "good"
    elif drop_pct < 25:
        return "warn"
    elif drop_pct < 40:
        return "danger"
    return "critical"


def severity_color(sev: str) -> str:
    return {"good": CLR_GOOD, "warn": CLR_WARN, "danger": CLR_DANGER, "critical": CLR_CRITICAL}.get(sev, CLR_GOOD)


# =========================================================================
#  SIDEBAR
# =========================================================================

def render_sidebar():
    """Render the sidebar navigation and return the selected page name."""
    with st.sidebar:
        st.markdown("""
        <div style="padding: 20px 16px 8px 16px;">
            <div style="font-size: 1.3rem; font-weight: 700; color: #F9FAFB;">
                \U0001f451 MenoQueen
            </div>
            <div style="font-size: 0.8rem; color: #6B7280; margin-top: 2px;">
                Quiz Analytics
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="section-header">OVERVIEW</div>', unsafe_allow_html=True)

        pages = [
            "\U0001f4ca  Dashboard",
            "\U0001f6a8  Drop-off Report",
            "\U0001f465  Quiz Responses",
            "\U0001f4b0  Shopify Impact",
            "\U0001f916  AI Analyst",
        ]

        # Map display names to section headers
        page = st.radio(
            "Navigation",
            pages,
            key="nav_page",
            label_visibility="collapsed",
        )

        st.markdown("---")

        # Data source status
        st.markdown('<div class="section-header">DATA SOURCES</div>', unsafe_allow_html=True)

        sources = [
            ("Klaviyo", bool(KLAVIYO_API_KEY)),
            ("GA4", _ga4_available()),
            ("Shopify", _shopify_available()),
            ("Claude AI", bool(ANTHROPIC_API_KEY)),
        ]
        for name, connected in sources:
            dot_class = "connected" if connected else "disconnected"
            status_text = "Connected" if connected else "Not configured"
            st.markdown(
                f'<div style="padding: 4px 16px; font-size: 0.8rem;">'
                f'<span class="status-dot status-dot--{dot_class}"></span>'
                f'<span style="color: {"#9CA3AF" if connected else "#4B5563"}">{name}</span>'
                f'<span style="float: right; font-size: 0.7rem; color: #4B5563;">{status_text}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        if st.button("\U0001f504  Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    return page


# =========================================================================
#  PAGE 1: DASHBOARD
# =========================================================================

def render_dashboard_page(df: pd.DataFrame, ga4_steps: dict | None, shopify_metrics: dict | None):
    st.markdown('<div class="page-title">\U0001f4ca Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Overview of your quiz funnel performance</div>', unsafe_allow_html=True)

    total = len(df)
    emails = int((df["email"] != "").sum()) if not df.empty else 0
    completed = int(df["quiz_completed"].sum()) if not df.empty else 0
    email_rate = round(emails / total * 100, 1) if total else 0
    completion_rate = round(completed / emails * 100, 1) if emails else 0
    overall = round(completed / total * 100, 1) if total else 0

    # -- Klaviyo KPI Row --
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Quiz Starts", f"{total:,}", source="klaviyo"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Emails Captured", f"{emails:,}", f"{email_rate}% of starts", source="klaviyo"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Completed", f"{completed:,}", f"{completion_rate}% of emails", source="klaviyo"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Overall Conversion", f"{overall}%", "Start to completion", source="klaviyo"), unsafe_allow_html=True)

    # -- Shopify KPI Row --
    if shopify_metrics:
        c1, c2, c3, c4 = st.columns(4)
        top_coupon = ""
        if shopify_metrics["coupon_counts"]:
            top_code = max(shopify_metrics["coupon_counts"], key=shopify_metrics["coupon_counts"].get)
            top_coupon = f"{top_code}: {shopify_metrics['coupon_counts'][top_code]}"
        with c1:
            st.markdown(metric_card("Revenue", f"${shopify_metrics['revenue']:,.2f}", source="shopify"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Orders", f"{shopify_metrics['total_orders']:,}", source="shopify"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Subscription Rate", f"{shopify_metrics['sub_pct']}%", source="shopify"), unsafe_allow_html=True)
        with c4:
            st.markdown(metric_card("Top Coupon", top_coupon or "None", source="shopify"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # -- Daily Trend --
    if not df.empty and not df["created"].isna().all():
        st.markdown('<div class="chart-title">Daily Quiz Starts</div>', unsafe_allow_html=True)
        daily = df.set_index("created").resample("D").size().reset_index(name="profiles")
        fig = px.area(daily, x="created", y="profiles", color_discrete_sequence=[CLR_KLAVIYO])
        fig.update_traces(fill="tozeroy", fillcolor="rgba(124, 58, 237, 0.15)")
        apply_chart_theme(fig)
        fig.update_layout(height=280, xaxis_title="", yaxis_title="New Profiles")
        st.plotly_chart(fig, use_container_width=True)

    # -- Bottom Row: Mini Funnel + Audience Snapshot --
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="chart-title">Funnel Snapshot</div>', unsafe_allow_html=True)
        funnel = compute_funnel(df)
        if not funnel.empty:
            key_steps = ["q1", "email-capture", "product-recommendation"]
            key_labels = ["Quiz Start", "Email Capture", "Product Page"]
            for i, (step_id, label) in enumerate(zip(key_steps, key_labels)):
                row = funnel[funnel["step"] == step_id]
                if row.empty:
                    continue
                count = int(row.iloc[0]["count"])
                pct = row.iloc[0]["pct"]
                sev = get_severity(100 - pct) if i > 0 else "good"
                color = severity_color(sev)
                st.markdown(f"""
                <div class="mini-funnel-label">
                    <span>{label}</span>
                    <span>{count:,} ({pct}%)</span>
                </div>
                <div class="mini-funnel-bar">
                    <div class="mini-funnel-fill" style="width: {max(pct, 5)}%; background: {color};">
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="chart-title">Audience Snapshot</div>', unsafe_allow_html=True)
        snapshot_items = [
            ("quiz_q1", "Top Symptom"),
            ("quiz_q9", "Top Stage"),
            ("quiz_q10", "Top Age Group"),
        ]
        for col_name, label in snapshot_items:
            dist = compute_answer_distribution(df, col_name)
            if not dist.empty:
                top = dist.iloc[0]
                total_answers = dist["count"].sum()
                pct = round(top["count"] / total_answers * 100, 1) if total_answers else 0
                st.markdown(f"""
                <div style="background: #1A1D24; border: 1px solid #2D3039; border-radius: 10px;
                            padding: 14px 16px; margin-bottom: 8px;">
                    <div style="font-size: 0.75rem; color: #6B7280; text-transform: uppercase;
                                letter-spacing: 0.04em; margin-bottom: 4px;">{label}</div>
                    <div style="font-size: 1.1rem; font-weight: 600; color: #F9FAFB;">
                        {top["answer"]}
                    </div>
                    <div style="font-size: 0.78rem; color: #9CA3AF;">{pct}% of respondents</div>
                </div>
                """, unsafe_allow_html=True)


# =========================================================================
#  PAGE 2: DROP-OFF REPORT
# =========================================================================

def render_dropoff_page(df: pd.DataFrame, ga4_steps: dict | None, ga4_error: str | None = None):
    st.markdown('<div class="page-title">\U0001f6a8 Drop-off Report</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Identify where users leave the quiz and what needs attention</div>', unsafe_allow_html=True)

    tab_full, tab_ga4, tab_klaviyo = st.tabs(["\U0001f50d  Full Funnel", "\U0001f310  GA4 Pre-Email", "\U0001f4e7  Klaviyo Post-Email"])

    with tab_full:
        _render_full_funnel_waterfall(df, ga4_steps)

    with tab_ga4:
        _render_ga4_funnel_tab(ga4_steps, ga4_error)

    with tab_klaviyo:
        _render_klaviyo_funnel_tab(df)


def _render_full_funnel_waterfall(df: pd.DataFrame, ga4_steps: dict | None):
    """Unified waterfall combining GA4 + Klaviyo data with severity indicators."""
    funnel = compute_funnel(df)
    if funnel.empty:
        st.info("No funnel data yet.")
        return

    # Build step data with drop-off calculations
    steps_data = []
    prev_count = None
    for _, row in funnel.iterrows():
        count = int(row["count"])
        ga4_count = ga4_steps.get(row["step"], 0) if ga4_steps else None
        drop_pct = 0
        lost = 0
        if prev_count is not None and prev_count > 0:
            lost = prev_count - count
            drop_pct = round(lost / prev_count * 100, 1)
        steps_data.append({
            "step": row["step"],
            "label": row["label"],
            "count": count,
            "pct": row["pct"],
            "ga4_count": ga4_count,
            "drop_pct": drop_pct,
            "lost": lost,
            "severity": get_severity(drop_pct) if prev_count is not None else "good",
        })
        prev_count = count

    # -- Attention Banner --
    problem_steps = [s for s in steps_data if s["severity"] in ("danger", "critical")]
    if problem_steps:
        worst = max(problem_steps, key=lambda s: s["drop_pct"])
        banner_class = "danger" if any(s["severity"] == "critical" for s in problem_steps) else "warn"
        st.markdown(f"""
        <div class="attention-banner attention-banner--{banner_class}">
            <div class="banner-icon">\u26a0\ufe0f</div>
            <div class="banner-text">
                <strong>{len(problem_steps)} step{"s" if len(problem_steps) > 1 else ""}</strong>
                {"have" if len(problem_steps) > 1 else "has"} drop-offs exceeding 25%.
                Biggest issue: <strong>{worst['label']}</strong> losing {worst['drop_pct']}% of users.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # -- Step Waterfall --
    for i, step in enumerate(steps_data):
        # Connector arrow (between steps)
        if i > 0 and step["lost"] > 0:
            sev = step["severity"]
            connector_class = f"step-connector--{sev}" if sev != "good" else ""
            arrow_text = f"\u2193 -{step['drop_pct']}% ({step['lost']:,} lost)"
            st.markdown(f'<div class="step-connector {connector_class}">{arrow_text}</div>', unsafe_allow_html=True)

        # Step card
        sev = step["severity"]
        badge_html = ""
        if sev == "danger":
            badge_html = '<span class="step-badge badge-attention">Attention</span>'
        elif sev == "critical":
            badge_html = '<span class="step-badge badge-critical">Critical</span>'

        ga4_html = ""
        if step["ga4_count"] and step["ga4_count"] > 0:
            ga4_html = f' &nbsp;|&nbsp; <span class="source-badge source-badge--ga4">GA4</span> {step["ga4_count"]:,} pageviews'

        card_html = f'<div class="step-card step-card--{sev}"><div class="step-name">{step["label"]}{badge_html}</div><div class="step-counts"><span class="source-badge source-badge--klaviyo">Klaviyo</span> {step["count"]:,} profiles ({step["pct"]}%){ga4_html}</div></div>'
        st.markdown(card_html, unsafe_allow_html=True)

    # -- Drop-off Heatmap --
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Where Users Drop Off</div>', unsafe_allow_html=True)

    heatmap_data = [s for s in steps_data if s["lost"] > 0]
    if heatmap_data:
        heatmap_df = pd.DataFrame(heatmap_data)
        colors = [severity_color(s) for s in heatmap_df["severity"]]
        fig = go.Figure(go.Bar(
            x=heatmap_df["lost"],
            y=heatmap_df["label"],
            orientation="h",
            marker=dict(color=colors),
            text=[f"-{d}%" for d in heatmap_df["drop_pct"]],
            textposition="auto",
            textfont=dict(color="#FFF", size=11),
        ))
        apply_chart_theme(fig)
        fig.update_layout(
            height=max(250, len(heatmap_data) * 36),
            yaxis=dict(autorange="reversed"),
            xaxis_title="Users Lost",
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_ga4_funnel_tab(ga4_steps: dict | None, ga4_error: str | None = None):
    if not ga4_steps:
        if ga4_error:
            st.warning(f"**GA4 connection error:** {ga4_error}")
        elif _ga4_available():
            st.info(
                "**GA4 connected but no data yet.** Pageview data can take 24-48 hours "
                "to appear after GA4 setup. Try again later."
            )
        else:
            st.info(
                "**GA4 not connected.** Add `GA4_PROPERTY_ID` and `GA4_CREDENTIALS_JSON` "
                "environment variables to see anonymous visitor data."
            )
        return

    records = []
    for step_id in QUIZ_STEPS_ORDER:
        views = ga4_steps.get(step_id, 0)
        records.append({"step": step_id, "label": STEP_LABELS.get(step_id, step_id), "pageviews": views})
    ga_df = pd.DataFrame(records)
    ga_df = ga_df[ga_df["pageviews"] > 0]

    if ga_df.empty:
        st.info("No GA4 pageview data for quiz steps yet. Data can take 24-48 hours to appear after GA4 setup.")
        return

    n = len(ga_df)
    palette = (CHART_COLORS * ((n // len(CHART_COLORS)) + 1))[:n]

    fig = go.Figure(go.Funnel(
        y=ga_df["label"],
        x=ga_df["pageviews"],
        textinfo="value+percent initial",
        marker=dict(color=palette),
    ))
    apply_chart_theme(fig)
    fig.update_layout(height=max(350, n * 36))
    st.plotly_chart(fig, use_container_width=True, key="ga4_funnel_chart")


def _render_klaviyo_funnel_tab(df: pd.DataFrame):
    funnel = compute_funnel(df)
    if funnel.empty:
        st.info("No funnel data yet.")
        return

    n = len(funnel)
    palette = (CHART_COLORS * ((n // len(CHART_COLORS)) + 1))[:n]

    fig = go.Figure(go.Funnel(
        y=funnel["label"],
        x=funnel["count"],
        textinfo="value+percent initial",
        marker=dict(color=palette),
    ))
    apply_chart_theme(fig)
    fig.update_layout(height=max(400, n * 36))
    st.plotly_chart(fig, use_container_width=True, key="klaviyo_funnel_chart")


# =========================================================================
#  PAGE 3: QUIZ RESPONSES
# =========================================================================

def render_responses_page(df: pd.DataFrame):
    st.markdown('<div class="page-title">\U0001f465 Quiz Responses</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Understand your audience through their quiz answers</div>', unsafe_allow_html=True)

    tab_key, tab_health, tab_lifestyle, tab_demo, tab_all = st.tabs([
        "\u2b50  Key Insights", "\U0001fa7a  Health", "\U0001f96c  Lifestyle",
        "\U0001f4ca  Demographics", "\U0001f4cb  Full Breakdown",
    ])

    with tab_key:
        col_l, col_r = st.columns(2)
        with col_l:
            _render_question_chart(df, "quiz_q1", "Primary Symptom (Q1)", chart_type="hbar", key_prefix="key")
        with col_r:
            _render_question_chart(df, "quiz_q9", "Menopause Stage (Q9)", chart_type="donut", key_prefix="key")

        col_l2, col_r2 = st.columns(2)
        with col_l2:
            _render_question_chart(df, "quiz_q10", "Age Range (Q10)", chart_type="bar", key_prefix="key")
        with col_r2:
            _render_question_chart(df, "quiz_q12", "Relief Status (Q12)", chart_type="donut", key_prefix="key")

    with tab_health:
        for qk in Q_HEALTH:
            _render_question_chart(df, qk, f"{QUESTION_LABELS[qk]} ({qk.replace('quiz_', '').upper()})", chart_type="hbar", key_prefix="health")

    with tab_lifestyle:
        for qk in Q_LIFESTYLE:
            _render_question_chart(df, qk, f"{QUESTION_LABELS[qk]} ({qk.replace('quiz_', '').upper()})", chart_type="hbar", key_prefix="lifestyle")

    with tab_demo:
        for qk in Q_DEMOGRAPHICS:
            _render_question_chart(df, qk, f"{QUESTION_LABELS[qk]} ({qk.replace('quiz_', '').upper()})", chart_type="bar", key_prefix="demo")

    with tab_all:
        for qk in QUIZ_Q_KEYS:
            label = QUESTION_LABELS.get(qk, qk)
            dist = compute_answer_distribution(df, qk)
            if dist.empty:
                continue
            with st.expander(f"{label} ({qk})"):
                fig = px.bar(
                    dist, x="count", y="answer", orientation="h",
                    color="count", color_continuous_scale=[[0, "#4C1D95"], [1, "#A78BFA"]],
                )
                apply_chart_theme(fig)
                fig.update_layout(
                    height=max(180, len(dist) * 36),
                    showlegend=False, coloraxis_showscale=False,
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True, key=f"all_{qk}")


def _render_question_chart(df: pd.DataFrame, col: str, title: str, chart_type: str = "hbar", key_prefix: str = ""):
    """Render a single question chart with dark theme."""
    st.markdown(f'<div class="chart-title">{title}</div>', unsafe_allow_html=True)
    dist = compute_answer_distribution(df, col)
    if dist.empty:
        st.info("No data yet.")
        return

    chart_key = f"{key_prefix}_{col}_{chart_type}" if key_prefix else f"{col}_{chart_type}"

    if chart_type == "hbar":
        fig = px.bar(
            dist, x="count", y="answer", orientation="h",
            color="count", color_continuous_scale=[[0, "#4C1D95"], [1, "#A78BFA"]],
        )
        apply_chart_theme(fig)
        fig.update_layout(
            height=max(220, len(dist) * 40),
            showlegend=False, coloraxis_showscale=False,
            yaxis=dict(autorange="reversed"),
        )
    elif chart_type == "donut":
        fig = px.pie(
            dist, values="count", names="answer",
            color_discrete_sequence=CHART_COLORS, hole=0.45,
        )
        apply_chart_theme(fig)
        fig.update_layout(height=320)
    elif chart_type == "bar":
        fig = px.bar(
            dist, x="answer", y="count",
            color="count", color_continuous_scale=[[0, "#4C1D95"], [1, "#A78BFA"]],
        )
        apply_chart_theme(fig)
        fig.update_layout(
            height=300,
            showlegend=False, coloraxis_showscale=False,
            xaxis_title="", yaxis_title="Count",
            xaxis=dict(type="category"),
        )
    else:
        return

    st.plotly_chart(fig, use_container_width=True, key=chart_key)


# =========================================================================
#  PAGE 4: SHOPIFY IMPACT
# =========================================================================

def render_shopify_page(df: pd.DataFrame, shopify_metrics: dict | None, shopify_orders: list[dict] | None):
    st.markdown('<div class="page-title">\U0001f4b0 Shopify Impact</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">See how your quiz funnel drives revenue</div>', unsafe_allow_html=True)

    if not shopify_metrics:
        st.markdown("""
        <div class="metric-card metric-card--shopify" style="text-align: center; padding: 40px;">
            <div style="font-size: 2rem; margin-bottom: 12px;">\U0001f6d2</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #F9FAFB; margin-bottom: 8px;">
                Connect Shopify to see revenue data
            </div>
            <div style="font-size: 0.85rem; color: #9CA3AF;">
                Add <code>SHOPIFY_STORE_DOMAIN</code> and <code>SHOPIFY_ACCESS_TOKEN</code>
                to your environment variables to unlock revenue attribution, order tracking, and coupon analysis.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    tab_revenue, tab_attribution, tab_coupons = st.tabs([
        "\U0001f4c8  Revenue Overview", "\U0001f3af  Attribution", "\U0001f3f7\ufe0f  Coupons",
    ])

    with tab_revenue:
        c1, c2, c3, c4 = st.columns(4)
        aov = shopify_metrics["revenue"] / shopify_metrics["total_orders"] if shopify_metrics["total_orders"] else 0
        with c1:
            st.markdown(metric_card("Revenue", f"${shopify_metrics['revenue']:,.2f}", source="shopify"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Orders", f"{shopify_metrics['total_orders']:,}", source="shopify"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Avg Order Value", f"${aov:,.2f}", source="shopify"), unsafe_allow_html=True)
        with c4:
            st.markdown(metric_card("Subscription %", f"{shopify_metrics['sub_pct']}%",
                                     f"{shopify_metrics['subscription']} sub / {shopify_metrics['onetime']} one-time", source="shopify"), unsafe_allow_html=True)

        # Subscription vs One-time pie
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="chart-title">Order Type Breakdown</div>', unsafe_allow_html=True)
        type_df = pd.DataFrame([
            {"Type": "Subscription", "Count": shopify_metrics["subscription"]},
            {"Type": "One-time", "Count": shopify_metrics["onetime"]},
        ])
        fig = px.pie(type_df, values="Count", names="Type",
                     color_discrete_sequence=[CLR_SHOPIFY, CLR_KLAVIYO], hole=0.45)
        apply_chart_theme(fig)
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

    with tab_attribution:
        total = len(df)
        emails = int((df["email"] != "").sum()) if not df.empty else 0
        completed = int(df["quiz_completed"].sum()) if not df.empty else 0
        orders = shopify_metrics["total_orders"]
        revenue = shopify_metrics["revenue"]

        rev_per_start = revenue / total if total else 0
        rev_per_email = revenue / emails if emails else 0
        conv_rate = round(orders / total * 100, 1) if total else 0

        st.markdown('<div class="chart-title">Quiz Funnel Revenue Attribution</div>', unsafe_allow_html=True)

        flow = [
            ("Quiz Starts", f"{total:,}", "", CLR_KLAVIYO),
            ("Emails Captured", f"{emails:,}", f"{round(emails/total*100,1) if total else 0}% capture rate", CLR_KLAVIYO),
            ("Quiz Completed", f"{completed:,}", f"{round(completed/emails*100,1) if emails else 0}% completion", CLR_KLAVIYO),
            ("Orders Placed", f"{orders:,}", f"{conv_rate}% of starts converted", CLR_SHOPIFY),
            ("Revenue Generated", f"${revenue:,.2f}", "", CLR_SHOPIFY),
        ]

        for i, (label, value, pct_text, color) in enumerate(flow):
            st.markdown(f"""
            <div class="attribution-row">
                <div>
                    <div class="attr-label">{label}</div>
                    <div class="attr-pct">{pct_text}</div>
                </div>
                <div class="attr-value" style="color: {color};">{value}</div>
            </div>
            """, unsafe_allow_html=True)
            if i < len(flow) - 1:
                st.markdown('<div class="attribution-arrow">\u2193</div>', unsafe_allow_html=True)

        # Key metrics
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("Revenue per Quiz Start", f"${rev_per_start:,.2f}", "Total revenue / starts", source="shopify"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Revenue per Email", f"${rev_per_email:,.2f}", "Total revenue / emails", source="shopify"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Start-to-Order Rate", f"{conv_rate}%", f"{orders} orders from {total} starts", source="shopify"), unsafe_allow_html=True)

    with tab_coupons:
        if not shopify_metrics["coupon_counts"]:
            st.info("No coupon usage data found in recent orders.")
            return

        st.markdown('<div class="chart-title">Coupon Code Usage</div>', unsafe_allow_html=True)
        coupon_df = pd.DataFrame(
            [(code, count) for code, count in shopify_metrics["coupon_counts"].items()],
            columns=["Coupon", "Orders"],
        ).sort_values("Orders", ascending=False)

        fig = px.bar(
            coupon_df, x="Orders", y="Coupon", orientation="h",
            color_discrete_sequence=[CLR_SHOPIFY],
        )
        apply_chart_theme(fig)
        fig.update_layout(height=max(200, len(coupon_df) * 40))
        fig.update_traces(texttemplate="%{x}", textposition="auto", textfont=dict(color="#FFF"))
        st.plotly_chart(fig, use_container_width=True)


# =========================================================================
#  PAGE 5: AI ANALYST
# =========================================================================

def render_ai_page(
    df: pd.DataFrame,
    ga4_steps: dict | None = None,
    shopify_metrics: dict | None = None,
):
    st.markdown('<div class="page-title">\U0001f916 AI Analyst</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Get AI-powered insights from Claude about your quiz funnel</div>', unsafe_allow_html=True)

    if not ANTHROPIC_API_KEY:
        st.markdown("""
        <div class="metric-card metric-card--ai" style="text-align: center; padding: 40px;">
            <div style="font-size: 2rem; margin-bottom: 12px;">\U0001f916</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #F9FAFB; margin-bottom: 8px;">
                Connect Claude AI to unlock insights
            </div>
            <div style="font-size: 0.85rem; color: #9CA3AF;">
                Add <code>ANTHROPIC_API_KEY</code> to your environment variables to enable
                AI-powered analysis of your quiz funnel data.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Active sources badges
    badges = ['<span class="source-badge source-badge--klaviyo">Klaviyo</span>']
    if ga4_steps:
        badges.append('<span class="source-badge source-badge--ga4">GA4</span>')
    if shopify_metrics:
        badges.append('<span class="source-badge source-badge--shopify">Shopify</span>')
    st.markdown(f'<div style="margin-bottom: 16px;">Analyzing: {" ".join(badges)}</div>', unsafe_allow_html=True)

    tab_snap, tab_compare, tab_ask = st.tabs([
        "\U0001f4f8  Snapshot", "\U0001f504  Compare Periods", "\U0001f4ac  Ask Anything",
    ])

    today = date.today()

    with tab_snap:
        col_s, col_e = st.columns(2)
        with col_s:
            snap_start = st.date_input("From", value=today - timedelta(days=30), key="snap_start")
        with col_e:
            snap_end = st.date_input("To", value=today, key="snap_end")

        if st.button("\U0001f50d  Analyze with Claude", key="btn_snap", type="primary"):
            with st.spinner("Claude is analyzing your quiz data..."):
                filtered = _filter_by_dates(df, snap_start, snap_end)
                if filtered.empty:
                    st.warning("No profiles in that date range.")
                else:
                    summary = build_data_summary(
                        filtered,
                        f"{snap_start.strftime('%b %d')} \u2013 {snap_end.strftime('%b %d, %Y')} ({len(filtered)} profiles)",
                        ga4_steps=ga4_steps,
                        shopify_metrics=shopify_metrics,
                    )
                    _run_analysis(summary, "snapshot", "")

    with tab_compare:
        st.caption("Quick presets")
        p1, p2, _ = st.columns([1, 1, 2])
        with p1:
            if st.button("Last 7d vs Previous 7d", key="preset_7d"):
                st.session_state["a_start"] = today - timedelta(days=14)
                st.session_state["a_end"] = today - timedelta(days=8)
                st.session_state["b_start"] = today - timedelta(days=7)
                st.session_state["b_end"] = today
        with p2:
            if st.button("This month vs Last month", key="preset_month"):
                first_this = today.replace(day=1)
                last_month_end = first_this - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                st.session_state["a_start"] = last_month_start
                st.session_state["a_end"] = last_month_end
                st.session_state["b_start"] = first_this
                st.session_state["b_end"] = today

        st.markdown("**Period A** (baseline / earlier)")
        a1, a2 = st.columns(2)
        with a1:
            a_start = st.date_input("Start", value=st.session_state.get("a_start", today - timedelta(days=14)), key="a_start")
        with a2:
            a_end = st.date_input("End", value=st.session_state.get("a_end", today - timedelta(days=8)), key="a_end")

        st.markdown("**Period B** (recent / concerning)")
        b1, b2 = st.columns(2)
        with b1:
            b_start = st.date_input("Start", value=st.session_state.get("b_start", today - timedelta(days=7)), key="b_start")
        with b2:
            b_end = st.date_input("End", value=st.session_state.get("b_end", today), key="b_end")

        custom_q = st.text_input(
            "Custom question (optional)",
            placeholder="e.g. Why did our completion rate drop this week?",
            key="cmp_question",
        )

        if st.button("\U0001f504  Compare with Claude", key="btn_cmp", type="primary"):
            with st.spinner("Claude is comparing the two periods..."):
                df_a = _filter_by_dates(df, a_start, a_end)
                df_b = _filter_by_dates(df, b_start, b_end)
                if df_a.empty and df_b.empty:
                    st.warning("No profiles in either date range.")
                else:
                    ga4_a, ga4_b = None, None
                    if _ga4_available():
                        try:
                            ga4_a = fetch_ga4_step_pageviews(a_start.isoformat(), a_end.isoformat())
                            ga4_b = fetch_ga4_step_pageviews(b_start.isoformat(), b_end.isoformat())
                        except Exception:
                            pass
                    summary = build_comparison_summary(
                        df, a_start, a_end, b_start, b_end,
                        ga4_steps_a=ga4_a, ga4_steps_b=ga4_b,
                        shopify_metrics_a=shopify_metrics,
                        shopify_metrics_b=shopify_metrics,
                    )
                    _run_analysis(summary, "comparison", custom_q)

    with tab_ask:
        st.markdown("""
        <div style="background: #1A1D24; border: 1px solid #2D3039; border-radius: 10px;
                    padding: 16px; margin-bottom: 16px;">
            <div style="font-size: 0.85rem; color: #9CA3AF;">
                Ask Claude any specific question about your quiz data. The latest data from all
                connected sources will be included automatically.
            </div>
        </div>
        """, unsafe_allow_html=True)

        question = st.text_area(
            "Your question",
            placeholder="e.g. What's causing the drop-off between Q3 and Q4? Is there a pattern in who completes vs who doesn't?",
            key="ask_question",
            height=100,
        )

        if st.button("\U0001f4ac  Ask Claude", key="btn_ask", type="primary"):
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Claude is thinking..."):
                    summary = build_data_summary(df, ga4_steps=ga4_steps, shopify_metrics=shopify_metrics)
                    _run_analysis(summary, "snapshot", question)

    # Display persisted result across all tabs
    if "ai_insights" in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state["ai_insights"])


# =========================================================================
#  MAIN
# =========================================================================

def main():
    inject_css()

    if not KLAVIYO_API_KEY:
        st.error("**KLAVIYO_API_KEY** environment variable is not set.")
        st.markdown(
            "Set it in your Railway service variables, your `.env` file, "
            "or export it in your shell before running the app."
        )
        st.stop()

    page = render_sidebar()

    # -- Fetch Klaviyo data (always required) --
    with st.spinner("Loading quiz data..."):
        try:
            profiles = fetch_quiz_profiles()
        except requests.exceptions.HTTPError as exc:
            st.error(f"Klaviyo API error: {exc.response.status_code}")
            st.stop()
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to Klaviyo API. Check your network and API key.")
            st.stop()
        except requests.exceptions.Timeout:
            st.error("Klaviyo API request timed out. Try again shortly.")
            st.stop()

    df = profiles_to_dataframe(profiles)

    if df.empty:
        st.warning("No quiz profiles found. Users may not have started the quiz yet.")
        st.stop()

    # -- Fetch GA4 data (optional) --
    ga4_steps = None
    ga4_error = None
    if _ga4_available():
        try:
            ga4_steps = fetch_ga4_step_pageviews()
        except Exception as e:
            ga4_error = str(e)

    # -- Fetch Shopify data (optional) --
    shopify_orders = None
    shopify_metrics = None
    if _shopify_available():
        try:
            shopify_orders = fetch_shopify_orders()
            shopify_metrics = compute_shopify_metrics(shopify_orders)
        except Exception:
            pass

    # -- Page Routing --
    if "\U0001f4ca" in page:  # Dashboard
        render_dashboard_page(df, ga4_steps, shopify_metrics)
    elif "\U0001f6a8" in page:  # Drop-off Report
        render_dropoff_page(df, ga4_steps, ga4_error=ga4_error)
    elif "\U0001f465" in page:  # Quiz Responses
        render_responses_page(df)
    elif "\U0001f4b0" in page:  # Shopify Impact
        render_shopify_page(df, shopify_metrics, shopify_orders)
    elif "\U0001f916" in page:  # AI Analyst
        render_ai_page(df, ga4_steps=ga4_steps, shopify_metrics=shopify_metrics)


if __name__ == "__main__":
    main()
