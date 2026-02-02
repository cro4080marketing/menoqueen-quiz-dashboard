import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MenoQueen Quiz Analytics",
    page_icon=":bar_chart:",
    layout="wide",
)

KLAVIYO_API_KEY = os.environ.get("KLAVIYO_API_KEY", "")
KLAVIYO_LIST_ID = os.environ.get("KLAVIYO_LIST_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
KLAVIYO_API_BASE = "https://a.klaviyo.com/api"
KLAVIYO_REVISION = "2024-02-15"

# Question labels mapped from the real Klaviyo property keys.
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

# Full ordered step list including result/educational pages.
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

# Prettify raw answer values for display.
def _pretty(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {KLAVIYO_API_KEY}",
        "revision": KLAVIYO_REVISION,
        "accept": "application/json",
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_quiz_profiles() -> list[dict]:
    """Fetch quiz profiles from Klaviyo.

    Uses the list endpoint when KLAVIYO_LIST_ID is set (recommended),
    otherwise falls back to fetching all profiles.
    Handles cursor-based pagination.
    """
    profiles: list[dict] = []

    if KLAVIYO_LIST_ID:
        url = f"{KLAVIYO_API_BASE}/lists/{KLAVIYO_LIST_ID}/profiles/"
    else:
        url = f"{KLAVIYO_API_BASE}/profiles/"

    params: dict = {"page[size]": 100}

    while url:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        profiles.extend(payload.get("data", []))

        next_link = payload.get("links", {}).get("next")
        if next_link:
            url = next_link
            params = {}
        else:
            url = None

    # When fetching without a list, keep only quiz profiles.
    if not KLAVIYO_LIST_ID:
        profiles = [
            p for p in profiles
            if p.get("attributes", {}).get("properties", {}).get("quiz_source") == "menoqueen_quiz"
        ]

    return profiles


def profiles_to_dataframe(profiles: list[dict]) -> pd.DataFrame:
    """Flatten Klaviyo profile JSON into a tidy DataFrame."""
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
# Metric helpers
# ---------------------------------------------------------------------------

def compute_answer_distribution(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Count occurrences of each answer value for a given quiz column."""
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
    """Estimate how many users reached each step or beyond.

    For profiles where quiz_current_step is empty we infer progress from which
    quiz answer fields are populated.  Completed profiles are placed at the
    final step.
    """
    step_index = {s: i for i, s in enumerate(QUIZ_STEPS_ORDER)}
    q_steps = [s for s in QUIZ_STEPS_ORDER if s.startswith("q")]

    def infer_rank(row):
        # Explicit current_step wins.
        explicit = step_index.get(row.get("current_step", ""), -1)
        if explicit >= 0:
            return explicit

        # Infer from answered questions: the last answered question tells us
        # the user reached at least that step.
        best = -1
        for qs in q_steps:
            val = row.get(qs, "")
            if val not in ("", None):
                rank = step_index.get(qs, -1)
                if rank > best:
                    best = rank
        # If they have an email, they passed email-capture.
        if row.get("email", "") and best >= 0:
            ec_rank = step_index.get("email-capture", best)
            if ec_rank > best:
                best = ec_rank
        return best

    if df.empty:
        return pd.DataFrame(columns=["step", "label", "count", "pct"])

    df = df.copy()
    df["step_rank"] = df.apply(infer_rank, axis=1)

    # Completed profiles made it through the entire funnel.
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


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

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


def render_funnel(df: pd.DataFrame):
    """Full quiz funnel including question, email, result, and product steps."""
    st.subheader("Quiz Funnel")
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
    """Horizontal bar chart of Q1 primary symptom answers."""
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
    """Donut chart of Q9 menopause stage."""
    st.subheader("Menopause Stage (Q9)")
    dist = compute_answer_distribution(df, "quiz_q9")
    if dist.empty:
        st.info("No stage data yet.")
        return
    fig = px.pie(
        dist, values="count", names="answer",
        color_discrete_sequence=px.colors.sequential.Purples_r,
        hole=0.4,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=300)
    st.plotly_chart(fig, use_container_width=True)


def render_age_range_chart(df: pd.DataFrame):
    """Bar chart of Q10 age range."""
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
    """Donut chart of Q12 relief status."""
    st.subheader("Relief Status (Q12)")
    dist = compute_answer_distribution(df, "quiz_q12")
    if dist.empty:
        st.info("No relief data yet.")
        return
    fig = px.pie(
        dist, values="count", names="answer",
        color_discrete_sequence=px.colors.sequential.Purples_r,
        hole=0.4,
    )
    fig.update_layout(margin=dict(l=20, r=20, t=10, b=10), height=300)
    st.plotly_chart(fig, use_container_width=True)


def render_all_questions_breakdown(df: pd.DataFrame):
    """Expandable section showing answer distributions for every question."""
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
        df.set_index("created")
        .resample("D")
        .size()
        .reset_index(name="profiles")
    )
    fig = px.area(
        daily, x="created", y="profiles",
        color_discrete_sequence=["#8E44AD"],
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=10, b=10), height=300,
        xaxis_title="", yaxis_title="New Profiles",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_raw_data(df: pd.DataFrame):
    with st.expander("Raw profile data"):
        st.dataframe(df, use_container_width=True, height=400)


# ---------------------------------------------------------------------------
# AI Insights (Claude via Anthropic API)
# ---------------------------------------------------------------------------

def build_data_summary(df: pd.DataFrame) -> str:
    """Build a concise text snapshot of all quiz data for the AI prompt."""
    total = len(df)
    emails = int((df["email"] != "").sum()) if not df.empty else 0
    completed = int(df["quiz_completed"].sum()) if not df.empty else 0

    lines = [
        "=== MenoQueen Quiz Data Snapshot ===",
        f"Total profiles: {total}",
        f"Emails captured: {emails} ({round(emails/total*100,1) if total else 0}%)",
        f"Completed: {completed} ({round(completed/total*100,1) if total else 0}%)",
        "",
    ]

    # Funnel with step-to-step drop-offs
    funnel = compute_funnel(df)
    if not funnel.empty:
        lines.append("=== Funnel (step → count → drop-off from previous) ===")
        prev = None
        for _, row in funnel.iterrows():
            drop = ""
            if prev is not None and prev > 0:
                lost = prev - row["count"]
                drop = f"  (lost {lost}, -{round(lost/prev*100,1)}%)"
            lines.append(f"  {row['label']}: {row['count']}{drop}")
            prev = row["count"]
        lines.append("")

    # Answer distributions per question
    lines.append("=== Answer Distributions ===")
    for qk in QUIZ_Q_KEYS:
        label = QUESTION_LABELS.get(qk, qk)
        dist = compute_answer_distribution(df, qk)
        if dist.empty:
            continue
        lines.append(f"\n{label} ({qk}):")
        for _, r in dist.iterrows():
            pct = round(r["count"] / total * 100, 1) if total else 0
            lines.append(f"  {r['answer']}: {r['count']} ({pct}%)")

    return "\n".join(lines)


def get_claude_insights(summary: str) -> str:
    """Call the Anthropic Messages API and return Claude's analysis."""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "system": (
                "You are a quiz funnel conversion analyst for MenoQueen, a menopause "
                "supplement brand. You analyze quiz completion data and provide actionable "
                "insights. Be specific, reference actual numbers from the data, and "
                "prioritize recommendations by potential revenue impact. Keep your analysis "
                "concise. Format with markdown headers (##) and bullet points."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Analyze this quiz funnel data. Identify:\n"
                        "1. The biggest drop-off points and likely causes\n"
                        "2. Patterns in who completes vs. who drops off\n"
                        "3. What the symptom/answer distributions reveal about the audience\n"
                        "4. 3-5 specific, actionable recommendations to improve conversion\n\n"
                        f"{summary}"
                    ),
                }
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    # Extract text from the first content block
    blocks = data.get("content", [])
    return blocks[0]["text"] if blocks else "No response received."


def render_ai_insights(df: pd.DataFrame):
    """Render the AI Insights section with an on-demand Analyze button."""
    st.subheader("AI Insights")

    if not ANTHROPIC_API_KEY:
        st.info(
            "Add **ANTHROPIC_API_KEY** as an environment variable to enable "
            "AI-powered drop-off analysis and recommendations."
        )
        return

    if st.button("Analyze with Claude"):
        with st.spinner("Claude is analyzing your quiz data..."):
            try:
                summary = build_data_summary(df)
                insights = get_claude_insights(summary)
                st.session_state["ai_insights"] = insights
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code
                if status == 401:
                    st.error("Invalid Anthropic API key. Check your ANTHROPIC_API_KEY.")
                elif status == 429:
                    st.error("Rate limited by Anthropic API. Wait a moment and try again.")
                else:
                    st.error(f"Anthropic API error: {status} – {exc.response.text[:300]}")
                return
            except requests.exceptions.Timeout:
                st.error("Claude API request timed out. Try again.")
                return
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
                return

    # Display persisted result
    if "ai_insights" in st.session_state:
        st.markdown(st.session_state["ai_insights"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not KLAVIYO_API_KEY:
        render_api_missing()

    render_header()

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
        st.warning(
            "No quiz profiles found. Users may not have started the quiz yet, "
            "or the list/filter returned no results."
        )
        st.stop()

    # -- KPIs --
    render_kpi_row(df)
    st.divider()

    # -- AI Insights (on-demand) --
    render_ai_insights(df)
    st.divider()

    # -- Funnel (full step progression including result pages) --
    render_funnel(df)
    st.divider()

    # -- Row 1: Primary symptom + Menopause stage --
    left, right = st.columns(2)
    with left:
        render_primary_symptom_chart(df)
    with right:
        render_menopause_stage_chart(df)

    st.divider()

    # -- Row 2: Age range + Relief status --
    left2, right2 = st.columns(2)
    with left2:
        render_age_range_chart(df)
    with right2:
        render_relief_status_chart(df)

    st.divider()

    # -- Daily trend --
    render_daily_trend(df)

    st.divider()

    # -- Full question breakdown --
    render_all_questions_breakdown(df)

    st.divider()

    # -- Raw data --
    render_raw_data(df)


if __name__ == "__main__":
    main()
