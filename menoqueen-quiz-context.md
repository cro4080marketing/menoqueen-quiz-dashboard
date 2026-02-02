# MenoQueen Quiz Dashboard - Complete Technical Context

## Overview
Alpine.js-based quiz funnel with persistent state, Klaviyo integration, and analytics tracking. Users complete symptom assessment quiz, get personalized product recommendations, and are nurtured via email if they don't complete.

---

## Data Storage Architecture

### LocalStorage Keys (Client-Side)
```javascript
// Quiz State
'menoqueen_quiz_answers_persistent' // JSON: { "q1": "hot-flashes", "q2": ["sleep", "mood"], ... }
'menoqueen_quiz_step_persistent'    // String: current step ID (e.g., "q1", "email-capture", "result-1")
'menoqueen_quiz_id'                 // String: unique session ID "quiz_1738502400000_abc123xyz"
'menoqueen_quiz_email'              // String: user's email after capture
'menoqueen_timer_end'               // Unix timestamp: countdown timer expiry
'menoqueen_coupon'                  // String: discount code (e.g., "QUEEN10")
```

### Klaviyo Profile Properties (via API)
```javascript
{
  // Identity
  "$email": "user@example.com",
  
  // Quiz Metadata
  "Quiz Completed": false,                    // Boolean: completion status
  "quiz_completed_at": "2026-02-02T14:30:00Z", // ISO timestamp or empty string
  "quiz_source": "menoqueen_quiz",
  "quiz_current_step": "result-2",            // Current step ID
  "quiz_state_url": "https://...",            // Restoration link with encoded state
  
  // Quiz Answers (dynamic based on questions)
  "quiz_q1": "hot-flashes",                   // Single choice
  "quiz_q2": "sleep, mood, weight",           // Multiple choice (comma-separated)
  "quiz_q3": "severe",                        // Symptom severity
  // ... more quiz answers
}
```

### URL Parameters (for Analytics)
```
Current format:
https://menoqueen.co/pages/quiz-1?step=q2

With state restoration:
https://menoqueen.co/pages/quiz-1?step=result-1&state=ABC123&coupon=QUEEN10

Where:
- step = current step ID (updated via pushState on each navigation)
- state = base64 encoded quiz state { a: answers, s: stepIndex, e: email, id: quizId }
- coupon = discount code from email campaign
```

---

## Quiz Flow Structure

### Step Types
1. **question** - User input (single/multiple choice)
2. **static** - Information page (auto-advances)
3. **email_capture** - Email gate (sends to Klaviyo)
4. **calculating** - Loading animation (auto-advances)
5. **product_recommendation** - Final product selection

### Typical Flow
```
q1 (symptoms) 
→ q2 (severity) 
→ email-capture 
→ preparing-summary (calculating, 5s auto-advance)
→ result-1 (educational content)
→ result-2 (more content)
→ result-3 (more content)
→ product-recommendation (final CTA)
```

### Example Quiz Data Structure
```json
{
  "steps": [
    {
      "id": "q1",
      "stepType": "question",
      "type": "multiple",
      "question": "What symptoms are you experiencing?",
      "options": [
        { "id": "hot-flashes", "label": "Hot flashes", "value": "hot-flashes" },
        { "id": "sleep", "label": "Sleep issues", "value": "sleep" }
      ],
      "required": true
    },
    {
      "id": "email-capture",
      "stepType": "email_capture",
      "headline": "Get Your Results",
      "required": true
    },
    {
      "id": "product-recommendation",
      "stepType": "product_select",
      "products": [
        {
          "id": "1-month",
          "variantId": "123456",
          "sellingPlanId": "789012",
          "bottles": 1,
          "subscriptionPrices": { "perBottle": 39, "total": 39, "save": 0 },
          "onetimePrices": { "perBottle": 49, "total": 49, "save": 0 }
        }
      ]
    }
  ]
}
```

---

## Key Events & Tracking

### User Actions Tracked
1. **Quiz Started** - First question answered
2. **Step Navigation** - Forward/back clicks (URL updates via pushState)
3. **Email Capture** - Klaviyo identify + list subscription
4. **Quiz Completed** - Reached product page
5. **Drop-off** - Session ends before completion (inferable from URL analytics)

### Klaviyo Events
```javascript
// On email capture
_learnq.push(['identify', { 
  '$email': email, 
  'Quiz Completed': false,
  'quiz_current_step': 'result-1',
  // ... all answers
}]);
_learnq.push(['track', 'Quiz Started', { ... }]);

// On navigation (updates current step)
_learnq.push(['identify', { 
  '$email': email,
  'quiz_current_step': 'result-2',
  'quiz_state_url': '...'
}]);

// On completion
_learnq.push(['identify', { 
  '$email': email, 
  'Quiz Completed': true,
  'quiz_completed_at': '2026-02-02T14:30:00Z'
}]);
_learnq.push(['track', 'Quiz Completed', { ... }]);
```

---

## Available Data Sources for Dashboard

### 1. Google Analytics (via URL tracking)
- **Pageviews by step**: `/pages/quiz-1?step=q1`, `?step=q2`, etc.
- **Funnel visualization**: Entry → Q1 → Q2 → Email → Results → Product
- **Drop-off rates**: % who leave at each step
- **Time on step**: Average duration per question
- **Traffic sources**: UTM parameters (when implemented)

### 2. Klaviyo API
**Endpoint**: `https://a.klaviyo.com/api/profiles/`

**Available Metrics**:
- Total quiz starters (profiles with `quiz_source = "menoqueen_quiz"`)
- Email capture rate (profiles with email vs. total sessions)
- Completion rate (profiles with `Quiz Completed = true`)
- Drop-off by step (group by `quiz_current_step`)
- Answer distribution (aggregate `quiz_q1`, `quiz_q2`, etc.)
- Time to complete (`quiz_completed_at` - first identify timestamp)

**Example Query**:
```
GET /api/profiles/?filter=equals(quiz_source,"menoqueen_quiz")
```

### 3. Shopify (Product Performance)
- Products purchased after quiz completion
- Revenue by product variant
- Subscription vs. one-time purchase ratio
- Coupon usage rates (discount code redemption)

---

## Key Metrics to Track

### Funnel Metrics
```
Quiz Views (GA pageview ?step=q1)
↓
Email Capture Rate = emails captured / quiz starts
↓
Quiz Completion Rate = completed / email captured
↓
Purchase Rate = orders / completed
↓
Overall Conversion = orders / quiz starts
```

### Step-Level Metrics
- **Drop-off Rate per Step**: % who don't proceed to next step
- **Answer Distribution**: What % chose each option
- **Time per Step**: Average duration before clicking "Next"
- **Back Button Usage**: How often users go backwards

### Business Metrics
- **Revenue per Quiz Start**: Total revenue / quiz starts
- **Customer Acquisition Cost**: Ad spend / quiz conversions
- **Email List Growth**: New subscribers from quiz
- **Average Order Value**: Revenue / orders (by product tier)

---

## Dashboard Requirements

### Real-Time Overview
- **Active Sessions**: Current users in quiz (last 5 min activity)
- **Today's Stats**: Starts, emails, completions, purchases
- **Conversion Funnel**: Visual flow with drop-off %

### Historical Analysis
- **Trend Charts**: Daily/weekly quiz starts, completions, revenue
- **Cohort Analysis**: Completion rate by start date
- **A/B Test Results**: Compare versions (if multiple quiz URLs)

### Answer Intelligence
- **Symptom Distribution**: What symptoms are most common?
- **Severity Breakdown**: Mild vs. moderate vs. severe
- **Product Selection**: Which tier do people choose?
- **Correlation**: Do certain answers predict purchase?

### Performance Alerts
- **Drop-off Spikes**: Alert if specific step sees >X% drop
- **Completion Rate Drop**: Alert if daily rate falls below threshold
- **Email Deliverability**: Monitor Klaviyo subscription failures

---

## Technical Integration Notes

### Data Access Methods

**Option 1: Klaviyo API** (Recommended for quiz data)
```python
import requests

headers = {
    'Authorization': 'Klaviyo-API-Key YOUR_KEY',
    'revision': '2024-02-15'
}

# Get all quiz profiles
response = requests.get(
    'https://a.klaviyo.com/api/profiles/',
    headers=headers,
    params={'filter': 'equals(quiz_source,"menoqueen_quiz")'}
)
```

**Option 2: Google Analytics API** (For URL tracking data)
```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient

# Get pageviews by step
request = RunReportRequest(
    dimensions=[{'name': 'pagePath'}],
    metrics=[{'name': 'screenPageViews'}],
    dimension_filter={'filter': {'field_name': 'pagePath', 'string_filter': {'value': '/pages/quiz-1'}}}
)
```

**Option 3: Shopify API** (For purchase data)
```python
import shopify

# Get orders with quiz source
orders = shopify.Order.find(
    status='any',
    created_at_min='2026-01-01'
)
```

### Data Refresh Strategy
- **Real-time**: Poll Klaviyo API every 60 seconds for active sessions
- **Hourly**: Update funnel metrics, answer distributions
- **Daily**: Aggregate completion rates, revenue metrics
- **On-demand**: Allow manual refresh for live presentations

---

## Example Dashboard Wireframe

```
┌─────────────────────────────────────────────────────────┐
│ MenoQueen Quiz Analytics Dashboard                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ TODAY'S PERFORMANCE                                      │
│ ┌───────────┬───────────┬───────────┬───────────┐       │
│ │ Starts    │ Emails    │ Complete  │ Orders    │       │
│ │ 247       │ 156 (63%) │ 98 (63%)  │ 12 (12%)  │       │
│ └───────────┴───────────┴───────────┴───────────┘       │
│                                                          │
│ FUNNEL VISUALIZATION                                     │
│ ┌──────────────────────────────────────────────┐        │
│ │ Q1: 247 (100%) ────────────────────┐         │        │
│ │ Q2: 198 (80%)  ──────────────┐     │         │        │
│ │ Email: 156 (63%) ──────┐     │     │         │        │
│ │ Results: 134 (54%) ──┐ │     │     │         │        │
│ │ Product: 98 (40%)  │ │ │     │     │         │        │
│ │ Purchase: 12 (5%)  │ │ │     │     │         │        │
│ └────────────────────┴─┴─┴─────┴─────┴─────────┘        │
│                                                          │
│ TOP SYMPTOMS (Last 7 Days)                              │
│ Hot flashes:    87% ████████████████████               │
│ Night sweats:   76% ████████████████                   │
│ Sleep issues:   71% ███████████████                    │
│ Brain fog:      65% ██████████████                     │
│                                                          │
│ PRODUCT SELECTION                                        │
│ 1-month (mild):      12% ███                           │
│ 2-month (moderate):  64% ████████████████ ⭐ POPULAR   │
│ 3-month (severe):    24% ██████                        │
└─────────────────────────────────────────────────────────┘
```

---

## Critical Context for Claude Code

1. **Data Lives in Klaviyo**: All quiz answers, completion status, and user progression are stored as Klaviyo profile properties

2. **URL Tracking is Live**: Every step navigation updates the URL (`?step=q1`), making Google Analytics funnel reports possible

3. **No Backend Database**: This is a client-side quiz, so all analytics must pull from Klaviyo API + Google Analytics

4. **Email is the Identifier**: Once captured, email is the primary key for tracking users across sessions

5. **State Encoding**: The `quiz_state_url` property contains a base64-encoded snapshot of the user's entire quiz state

6. **Real Product IDs**: The quiz outputs actual Shopify variant IDs and selling plan IDs for subscription purchases

---

## Suggested Dashboard Tech Stack

**Frontend**: 
- Streamlit (Python) - Fast, interactive, perfect for internal dashboards
- OR Next.js + Recharts (if you want it customer-facing)

**Backend**:
- Python FastAPI to fetch/cache Klaviyo + GA data
- Scheduled jobs to refresh metrics hourly

**Database** (optional):
- PostgreSQL to store historical snapshots
- Avoids hitting Klaviyo API rate limits

---

## Project Goal

Build a comprehensive analytics dashboard that shows:
1. Real-time quiz funnel performance
2. Historical trends and cohort analysis
3. Answer distribution and symptom insights
4. Revenue attribution and product performance
5. Actionable alerts for drop-offs and anomalies

The dashboard should pull from Klaviyo API as primary data source, optionally integrate Google Analytics for URL-level tracking, and provide both executive summary view and detailed drill-downs.
