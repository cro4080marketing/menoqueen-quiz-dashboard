# MenoQueen Quiz Analytics Dashboard

Streamlit dashboard that connects to Klaviyo to display quiz funnel metrics, symptom distributions, and product selection breakdowns.

## Requirements

- Python 3.10+
- A Klaviyo private API key (`pk_...`)

## Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env
# Edit .env with your real KLAVIYO_API_KEY

# Run (with env vars loaded)
export $(cat .env | xargs) && streamlit run app.py
```

The app will open at `http://localhost:8501`.

## Deploy to Railway

1. Push this repo to GitHub.
2. Create a new project on [Railway](https://railway.com) and connect the repo.
3. Add the environment variable **KLAVIYO_API_KEY** in the Railway service settings.
4. Railway reads `railway.json` automatically — no Procfile needed.
5. Deploy. The health check at `/_stcore/health` will confirm the app is running.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `KLAVIYO_API_KEY` | Yes | Klaviyo private API key |
| `KLAVIYO_LIST_ID` | No | Scope to a specific Klaviyo list |

## Dashboard Sections

- **KPI row** — total profiles, email capture rate, completion rate, overall conversion
- **Funnel chart** — visual funnel from Q1 through product recommendation
- **Drop-off view** — bar chart of where users are currently stuck
- **Symptom distribution** — horizontal bar chart of Q1 multi-select answers
- **Severity breakdown** — donut chart of Q3 severity answers
- **Daily trend** — area chart of new quiz profiles over time
- **Raw data** — expandable table of all profile records

## Data Flow

The dashboard queries the Klaviyo Profiles API filtering on `quiz_source = "menoqueen_quiz"`. All quiz answers, completion status, and current step are stored as Klaviyo profile properties by the client-side quiz. Results are cached for 5 minutes; click **Refresh data** to force a reload.
