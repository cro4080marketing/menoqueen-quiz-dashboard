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
    page_icon=":bar_chart:",
    layout="wide",
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


def _pretty(value: str) -> str:
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
    """Query GA4 for pageviews per quiz step.

    Returns dict like {"q1": 500, "q2": 420, "email-capture": 310, ...}.
    """
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
        # Extract ?step= parameter from the URL path
        match = re.search(r"[?&]step=([^&]+)", url_path)
        if match:
            step = match.group(1)
        else:
            step = "q1"  # Landing on the quiz page without ?step= means Q1
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

        # Shopify uses Link header for pagination
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
#  UI COMPONENTS
# =========================================================================

def render_api_missing():
    st.error("**KLAVIYO_API_KEY** environment variable is not set.")
    st.markdown(
        "Set it in your Railway service variables, your `.env` file, "
        "or export it in your shell before running the app.\n\n"
        "```bash\nexport KLAVIYO_API_KEY=pk_xxxxxxxxxxxx\n```"
    )
    st.stop()


def render_header():
    st.title("MenoQueen Quiz Analytics")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()


def render_kpi_row(df: pd.DataFrame):
    total = len(df)
    emails = int((df["email"] != "").sum()) if not df.empty else 0
    completed = int(df["quiz_completed"].sum()) if not df.empty else 0
    email_rate = round(emails / total * 100, 1) if total else 0
    completion_rate = round(completed / emails * 100, 1) if emails else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quiz Profiles", f"{total:,}")
    c2.metric("Emails Captured", f"{emails:,}", f"{email_rate}% of starts")
    c3.metric("Completed", f"{completed:,}", f"{completion_rate}% of emails")
    c4.metric(
        "Overall Conversion",
        f"{round(completed / total * 100, 1) if total else 0}%",
    )


def render_shopify_kpis(metrics: dict):
    """Render Shopify revenue KPI row."""
    st.subheader("Shopify Revenue")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders", f"{metrics['total_orders']:,}")
    c2.metric("Revenue", f"${metrics['revenue']:,.2f}")
    c3.metric("Subscription %", f"{metrics['sub_pct']}%")
    top_coupon = ""
    if metrics["coupon_counts"]:
        top_code = max(metrics["coupon_counts"], key=metrics["coupon_counts"].get)
        top_coupon = f"{top_code}: {metrics['coupon_counts'][top_code]}"
    c4.metric("Top Coupon", top_coupon or "None")


def render_ga4_funnel(step_counts: dict):
    """Bar chart of GA4 pageviews per quiz step."""
    st.subheader("Full Funnel - Google Analytics (pageviews)")
    # Build ordered data
    records = []
    for step_id in QUIZ_STEPS_ORDER:
        views = step_counts.get(step_id, 0)
        records.append({
            "step": step_id,
            "label": STEP_LABELS.get(step_id, step_id),
            "pageviews": views,
        })
    ga_df = pd.DataFrame(records)
    ga_df = ga_df[ga_df["pageviews"] > 0]

    if ga_df.empty:
        st.info("No GA4 pageview data for quiz steps yet.")
        return

    colors = px.colors.sequential.Purples_r
    n = len(ga_df)
    palette = (colors * ((n // len(colors)) + 1))[:n]

    fig = go.Figure(go.Funnel(
        y=ga_df["label"],
        x=ga_df["pageviews"],
        textinfo="value+percent initial",
        marker=dict(color=palette),
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10),
        height=max(350, n * 32),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_funnel(df: pd.DataFrame):
    st.subheader("Quiz Funnel - Klaviyo (post-email)")
    funnel = compute_funnel(df)
    if funnel.empty:
        st.info("No funnel data yet.")
        return

    colors = px.colors.sequential.Purples_r
    n = len(funnel)
    palette = (colors * ((n // len(colors)) + 1))[:n]

    fig = go.Figure(go.Funnel(
        y=funnel["label"],
        x=funnel["count"],
        textinfo="value+percent initial",
        marker=dict(color=palette),
    ))
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10),
        height=max(400, n * 32),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_primary_symptom_chart(df: pd.DataFrame):
    st.subheader("Primary Symptom (Q1)")
    dist = compute_answer_distribution(df, "quiz_q1")
    if dist.empty:
        st.info("No symptom data yet.")
        return
    fig = px.bar(
        dist, x="count", y="answer", orientation="h",
        color="count", color_continuous_scale="Purples",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10),
        height=max(220, len(dist) * 40),
        showlegend=False, coloraxis_showscale=False,
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_menopause_stage_chart(df: pd.DataFrame):
    st.subheader("Menopause Stage (Q9)")
    dist = compute_answer_distribution(df, "quiz_q9")
    if dist.empty:
        st.info("No stage data yet.")
        return
    fig = px.pie(
        dist, values="count", names="answer",
        color_discrete_sequence=px.colors.sequential.Purples_r, hole=0.4,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=300)
    st.plotly_chart(fig, use_container_width=True)


def render_age_range_chart(df: pd.DataFrame):
    st.subheader("Age Range (Q10)")
    dist = compute_answer_distribution(df, "quiz_q10")
    if dist.empty:
        st.info("No age data yet.")
        return
    fig = px.bar(
        dist, x="answer", y="count",
        color="count", color_continuous_scale="Purples",
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10), height=300,
        showlegend=False, coloraxis_showscale=False,
        xaxis_title="Age Range", yaxis_title="Count",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_relief_status_chart(df: pd.DataFrame):
    st.subheader("Relief Status (Q12)")
    dist = compute_answer_distribution(df, "quiz_q12")
    if dist.empty:
        st.info("No relief data yet.")
        return
    fig = px.pie(
        dist, values="count", names="answer",
        color_discrete_sequence=px.colors.sequential.Purples_r, hole=0.4,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=300)
    st.plotly_chart(fig, use_container_width=True)


def render_all_questions_breakdown(df: pd.DataFrame):
    st.subheader("Full Question Breakdown")
    for qk in QUIZ_Q_KEYS:
        label = QUESTION_LABELS.get(qk, qk)
        dist = compute_answer_distribution(df, qk)
        if dist.empty:
            continue
        with st.expander(f"{label} ({qk})"):
            fig = px.bar(
                dist, x="count", y="answer", orientation="h",
                color="count", color_continuous_scale="Purples",
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=max(180, len(dist) * 36),
                showlegend=False, coloraxis_showscale=False,
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)


def render_daily_trend(df: pd.DataFrame):
    st.subheader("Daily Quiz Starts")
    if df.empty or df["created"].isna().all():
        st.info("No time-series data available.")
        return
    daily = (
        df.set_index("created").resample("D").size().reset_index(name="profiles")
    )
    fig = px.area(daily, x="created", y="profiles", color_discrete_sequence=["#8E44AD"])
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10), height=300,
        xaxis_title="", yaxis_title="New Profiles",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_raw_data(df: pd.DataFrame):
    with st.expander("Raw profile data"):
        st.dataframe(df, use_container_width=True, height=400)


# =========================================================================
#  AI INSIGHTS (Claude via Anthropic API)
# =========================================================================

def _filter_by_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df.empty or df["created"].isna().all():
        return df
    mask = (df["created"].dt.date >= start) & (df["created"].dt.date <= end)
    return df.loc[mask]


def _ga4_summary_block(ga4_steps: dict) -> str:
    """Format GA4 step pageviews as a text block for the AI prompt."""
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
    """Format Shopify metrics as a text block for the AI prompt."""
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
    """Build a concise text snapshot including all available data sources."""
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

    # GA4 funnel (anonymous visitors)
    if ga4_steps:
        lines.append(_ga4_summary_block(ga4_steps))
        lines.append("")

    # Klaviyo funnel (post-email)
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

    # Shopify revenue
    if shopify_metrics:
        lines.append(_shopify_summary_block(shopify_metrics))
        lines.append("")

    # Answer distributions
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
    label_a = f"PERIOD A: {start_a.strftime('%b %d')} – {end_a.strftime('%b %d, %Y')} ({len(df_a)} profiles)"
    label_b = f"PERIOD B: {start_b.strftime('%b %d')} – {end_b.strftime('%b %d, %Y')} ({len(df_b)} profiles)"
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
            "1. Key metric changes between the periods (completion rate, email capture rate, drop-off shifts, revenue changes)\n"
            "2. Which funnel steps got worse (or better) and by how much\n"
            "3. Any shifts in answer distributions that could explain behaviour changes\n"
            "4. Revenue impact — did order volume or subscription rates change?\n"
            "5. 3-5 specific, prioritised recommendations to fix any declines\n\n"
        )
    else:
        user_content = (
            "Analyze this quiz funnel data. Identify:\n"
            "1. The biggest drop-off points and likely causes (use GA4 data for pre-email, Klaviyo for post-email)\n"
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
            st.error(f"Anthropic API error: {status} – {exc.response.text[:300]}")
    except requests.exceptions.Timeout:
        st.error("Claude API request timed out. Try again.")
    except Exception as exc:
        st.error(f"Unexpected error: {exc}")


def render_ai_insights(
    df: pd.DataFrame,
    ga4_steps: dict | None = None,
    shopify_metrics: dict | None = None,
):
    """Render AI Insights with Snapshot and Comparison modes, fed by all sources."""
    st.subheader("AI Insights")

    if not ANTHROPIC_API_KEY:
        st.info(
            "Add **ANTHROPIC_API_KEY** as an environment variable to enable "
            "AI-powered drop-off analysis and recommendations."
        )
        return

    # Show which data sources are active
    sources = ["Klaviyo"]
    if ga4_steps:
        sources.append("GA4")
    if shopify_metrics:
        sources.append("Shopify")
    st.caption(f"Data sources: {', '.join(sources)}")

    mode = st.radio(
        "Analysis type", ["Snapshot", "Comparison"], horizontal=True, key="ai_mode",
    )

    today = date.today()

    if mode == "Snapshot":
        col_s, col_e = st.columns(2)
        with col_s:
            snap_start = st.date_input("From", value=today - timedelta(days=30), key="snap_start")
        with col_e:
            snap_end = st.date_input("To", value=today, key="snap_end")

        custom_q = st.text_input(
            "Question for Claude (optional)",
            placeholder="e.g. Why is the drop-off so high after email capture?",
            key="snap_question",
        )

        if st.button("Analyze with Claude", key="btn_snap"):
            with st.spinner("Claude is analyzing your quiz data..."):
                filtered = _filter_by_dates(df, snap_start, snap_end)
                if filtered.empty:
                    st.warning("No profiles in that date range.")
                else:
                    summary = build_data_summary(
                        filtered,
                        f"{snap_start.strftime('%b %d')} – {snap_end.strftime('%b %d, %Y')} ({len(filtered)} profiles)",
                        ga4_steps=ga4_steps,
                        shopify_metrics=shopify_metrics,
                    )
                    _run_analysis(summary, "snapshot", custom_q)

    else:  # Comparison
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
            a_start = st.date_input(
                "Start", value=st.session_state.get("a_start", today - timedelta(days=14)), key="a_start",
            )
        with a2:
            a_end = st.date_input(
                "End", value=st.session_state.get("a_end", today - timedelta(days=8)), key="a_end",
            )

        st.markdown("**Period B** (recent / concerning)")
        b1, b2 = st.columns(2)
        with b1:
            b_start = st.date_input(
                "Start", value=st.session_state.get("b_start", today - timedelta(days=7)), key="b_start",
            )
        with b2:
            b_end = st.date_input(
                "End", value=st.session_state.get("b_end", today), key="b_end",
            )

        custom_q = st.text_input(
            "Question for Claude (optional)",
            placeholder="e.g. Why did our completion rate drop this week?",
            key="cmp_question",
        )

        if st.button("Compare with Claude", key="btn_cmp"):
            with st.spinner("Claude is comparing the two periods..."):
                df_a = _filter_by_dates(df, a_start, a_end)
                df_b = _filter_by_dates(df, b_start, b_end)
                if df_a.empty and df_b.empty:
                    st.warning("No profiles in either date range.")
                else:
                    # Fetch period-specific GA4 data if available
                    ga4_a, ga4_b = None, None
                    if _ga4_available():
                        try:
                            ga4_a = fetch_ga4_step_pageviews(a_start.isoformat(), a_end.isoformat())
                            ga4_b = fetch_ga4_step_pageviews(b_start.isoformat(), b_end.isoformat())
                        except Exception:
                            pass  # Graceful — comparison works without GA4

                    summary = build_comparison_summary(
                        df, a_start, a_end, b_start, b_end,
                        ga4_steps_a=ga4_a, ga4_steps_b=ga4_b,
                        shopify_metrics_a=shopify_metrics,
                        shopify_metrics_b=shopify_metrics,
                    )
                    _run_analysis(summary, "comparison", custom_q)

    # Display persisted result
    if "ai_insights" in st.session_state:
        st.divider()
        st.markdown(st.session_state["ai_insights"])


# =========================================================================
#  MAIN
# =========================================================================

def main():
    if not KLAVIYO_API_KEY:
        render_api_missing()

    render_header()

    # -- Fetch Klaviyo data (always required) --
    with st.spinner("Fetching quiz profiles from Klaviyo..."):
        try:
            profiles = fetch_quiz_profiles()
        except requests.exceptions.HTTPError as exc:
            st.error(f"Klaviyo API error: {exc.response.status_code} – {exc.response.text[:300]}")
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
    if _ga4_available():
        try:
            ga4_steps = fetch_ga4_step_pageviews()
        except Exception as exc:
            st.warning(f"GA4 data unavailable: {exc}")

    # -- Fetch Shopify data (optional) --
    shopify_orders = None
    shopify_metrics = None
    if _shopify_available():
        try:
            shopify_orders = fetch_shopify_orders()
            shopify_metrics = compute_shopify_metrics(shopify_orders)
        except Exception as exc:
            st.warning(f"Shopify data unavailable: {exc}")

    # -- KPIs --
    render_kpi_row(df)
    if shopify_metrics:
        render_shopify_kpis(shopify_metrics)
    st.divider()

    # -- AI Insights (on-demand, fed by all sources) --
    render_ai_insights(df, ga4_steps=ga4_steps, shopify_metrics=shopify_metrics)
    st.divider()

    # -- Funnels --
    if ga4_steps:
        render_ga4_funnel(ga4_steps)
        st.divider()
    render_funnel(df)
    st.divider()

    # -- Charts --
    left, right = st.columns(2)
    with left:
        render_primary_symptom_chart(df)
    with right:
        render_menopause_stage_chart(df)

    st.divider()

    left2, right2 = st.columns(2)
    with left2:
        render_age_range_chart(df)
    with right2:
        render_relief_status_chart(df)

    st.divider()

    render_daily_trend(df)
    st.divider()

    render_all_questions_breakdown(df)
    st.divider()

    render_raw_data(df)


if __name__ == "__main__":
    main()
