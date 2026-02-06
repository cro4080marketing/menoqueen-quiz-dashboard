# Quiz Funnel Analytics & Monitoring System - Context Document

## Project Overview

### Purpose
Build a comprehensive analytics and monitoring system for medical questionnaire funnels at Get Thin MD. The system should provide real-time insights, anomaly detection, and AI-powered optimization recommendations for telemedicine quiz funnels built with Embeddables.

### Business Context
- **Company**: Get Thin MD (telemedicine company offering weight loss, hair loss, skincare, sleep treatments)
- **Agency**: 4080 Marketing (CRO and development agency)
- **Primary Use Case**: Monitor and optimize complex medical questionnaires that route patients to appropriate treatment protocols
- **Key Challenge**: Multiple treatment verticals (GLP-1, NAD+, hair loss) with complex conditional logic requiring precise monitoring of drop-off points to identify issues quickly

### Success Metrics
- Reduce time to identify funnel issues from hours to minutes
- Increase visibility into step-by-step conversion performance
- Enable data-driven A/B test prioritization
- Improve overall funnel conversion rates through faster iteration

---

## Technical Stack Recommendations

### Backend
- **Framework**: Node.js with Express or Next.js API routes
- **Database**: PostgreSQL for historical data storage
- **Caching**: Redis for real-time metrics and alerts
- **Analytics Processing**: Python scripts for statistical analysis (optional)

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **UI Library**: Shadcn/ui + Tailwind CSS
- **Charts**: Recharts or Chart.js
- **State Management**: React Context or Zustand

### Integrations
- **Embeddables API**: Quiz funnel data source
- **Slack API**: Alert notifications and daily reports
- **Apify API**: Screenshot capture and visual analysis (Phase 2)
- **OpenAI/Anthropic API**: AI-powered analysis and recommendations

### Infrastructure
- **Hosting**: Vercel (frontend + API routes) or Railway/Render
- **Cron Jobs**: Vercel Cron or separate scheduler for daily reports
- **Environment**: Docker for local development consistency

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                            │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  Dashboard   │  │   Alerts     │  │  Recommendations   │   │
│  │  Overview    │  │   Center     │  │    & Testing       │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API LAYER (Next.js)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Funnel    │  │    Alert     │  │   AI Analysis       │   │
│  │   Analytics │  │   Detection  │  │   & Recommendations │   │
│  │   Endpoints │  │   Service    │  │   Service           │   │
│  └─────────────┘  └──────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER & PROCESSING                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │  PostgreSQL │  │    Redis     │  │   Background        │   │
│  │  Historical │  │  Real-time   │  │   Jobs & Cron       │   │
│  │  Data Store │  │  Cache       │  │   Scheduler         │   │
│  └─────────────┘  └──────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTEGRATIONS                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ Embeddables │  │  Slack API   │  │   Apify API         │   │
│  │    API      │  │  Webhooks    │  │   (Screenshots)     │   │
│  └─────────────┘  └──────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Data Collection**: Scheduled jobs fetch funnel data from Embeddables API every 15-30 minutes
2. **Data Storage**: Raw data stored in PostgreSQL, aggregated metrics cached in Redis
3. **Alert Detection**: Background service compares current metrics against baselines (1-day, 7-day)
4. **Notifications**: Anomalies trigger Slack webhooks with contextual information
5. **Daily Reports**: Cron job (runs at configured time) generates comprehensive analysis and sends to Slack
6. **Dashboard**: Real-time queries to database with Redis caching for performance

---

## Core Features - Detailed Specifications

### 1. Dashboard Overview

#### Main Metrics Cards
- **Total Funnel Starts** (current period)
- **Overall Conversion Rate** (start to completion)
- **Average Drop-off Rate** (across all steps)
- **Critical Steps** (steps with >30% drop-off)

#### Funnel Visualization
- **Sankey Diagram** or **Funnel Chart** showing flow from step to step
- Each step shows:
  - Step name/number
  - Total entries
  - Total exits
  - Conversion rate to next step
  - Drop-off rate
  - Comparison indicator (vs previous period)

#### Date Range Selector
- **Preset Ranges**: Today, Yesterday, Last 7 Days, Last 30 Days, Last 90 Days
- **Custom Range**: Start date + End date picker
- **Comparison Mode**: Toggle to compare two date ranges side-by-side

#### Funnel Selector
- Dropdown to switch between different quiz funnels
- Auto-detect available funnels from Embeddables API
- Show funnel metadata (total steps, last updated, status)

#### Performance Trends
- **Line Chart**: Conversion rate trend over time (daily granularity)
- **Heatmap**: Drop-off rates by step and day of week
- **Table View**: Detailed step-by-step metrics with sortable columns

---

### 2. Alert System

#### Alert Triggers

**Drop-off Rate Anomalies**
- Trigger if step drop-off rate increases by >15% vs previous day
- Trigger if step drop-off rate increases by >10% vs 7-day average
- Severity: Critical if drop-off >50%, Warning if 30-50%

**Conversion Rate Anomalies**
- Trigger if overall conversion drops by >20% vs previous day
- Trigger if overall conversion drops by >15% vs 7-day average

**Volume Anomalies**
- Trigger if funnel starts decrease by >30% vs previous day
- Trigger if funnel starts decrease by >25% vs 7-day average

**Step-Specific Patterns**
- Identify if a specific step suddenly has unusual behavior
- Compare step performance against its historical baseline

#### Alert Data Model

```typescript
interface Alert {
  id: string;
  timestamp: Date;
  funnelId: string;
  funnelName: string;
  severity: 'critical' | 'warning' | 'info';
  type: 'drop_off' | 'conversion' | 'volume' | 'step_anomaly';
  stepNumber?: number;
  stepName?: string;
  
  // Metrics
  currentValue: number;
  previousDayValue: number;
  sevenDayAverage: number;
  percentageChange: number;
  
  // Context
  message: string;
  recommendation?: string;
  
  // Status
  status: 'active' | 'resolved' | 'acknowledged';
  acknowledgedBy?: string;
  resolvedAt?: Date;
}
```

#### Slack Alert Format

```
🚨 **CRITICAL ALERT**: High Drop-off Detected

**Funnel**: Main Weight Loss Questionnaire
**Step**: Step 3 - Medical History (BMI Entry)
**Issue**: Drop-off rate increased by 47%

📊 **Metrics**:
• Current drop-off: 42% (vs 28.5% yesterday)
• 7-day average: 29.8%
• Change: +47% vs yesterday, +41% vs 7-day avg

⚠️ **Impact**:
• ~150 additional users dropping at this step today
• Estimated revenue impact: $4,500 (based on avg customer value)

💡 **Possible Causes**:
• Form validation error introduced in recent deploy
• API timeout on BMI calculation
• UI/UX change causing confusion
• Mobile performance degradation

🔗 **Actions**:
• [View Dashboard](https://dashboard.example.com/funnel/main-wl?step=3)
• [Check Recent Deploys](https://vercel.com/deployments)
• [Acknowledge Alert](https://dashboard.example.com/alerts/alert-123)
```

---

### 3. Daily Report

#### Report Timing
- Scheduled to run at 8:00 AM EST daily
- Covers previous 24 hours (midnight to midnight)
- Compares to day before yesterday for trend analysis

#### Report Contents

**Executive Summary**
- Overall conversion rate (with trend indicator)
- Total funnel starts (with trend indicator)
- Top 3 performing steps
- Top 3 underperforming steps
- Critical issues requiring attention

**Step-by-Step Analysis**
For each funnel step:
- Step name and number
- Total entries
- Total exits (drop-offs)
- Conversion rate to next step
- Trend vs previous day (% change)
- Status indicator (✅ Normal, ⚠️ Warning, 🚨 Critical)

**AI-Powered Insights**
Using Claude API to analyze the data and provide:
- **Main Blockers**: Identify the 2-3 steps causing the most friction
- **Pattern Recognition**: Detect unusual patterns (e.g., "Step 5 has 3x higher drop-off on mobile")
- **Correlation Analysis**: Link drops to potential causes (e.g., "Drop correlates with deployment timestamp")
- **Recovery Opportunities**: Suggest quick wins to improve conversion

**Trend Analysis**
- Week-over-week comparison
- Month-over-month comparison
- Seasonal patterns (if applicable)

#### Slack Report Format

```
📊 **Daily Quiz Funnel Report** - Jan 15, 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 **EXECUTIVE SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Overall Performance**:
• Conversion Rate: 23.4% (↓ 3.2% vs yesterday)
• Funnel Starts: 1,247 (↑ 8.5% vs yesterday)
• Completions: 292 (↑ 4.1% vs yesterday)

**Status**: ⚠️ **ATTENTION NEEDED**

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 **AI ANALYSIS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Main Blocker Identified**:
Step 4 (Insurance Information) is the primary conversion killer today. Drop-off increased from 18% to 31% (+72% change). This step is seeing unusual friction specifically on mobile devices (Safari).

**Root Cause Analysis**:
1. Timeline correlation: Drop-off spike began at 2:47 PM, coinciding with deploy #abc123
2. Device pattern: Desktop drop-off remained stable at 19%, but mobile spiked to 45%
3. Validation errors: 23% of users encountering "Invalid insurance provider" error

**Impact**:
• Estimated ~160 additional drop-offs today
• Potential revenue impact: ~$4,800 (at $30 avg customer value)

**Recommended Actions**:
1. [URGENT] Review deploy #abc123 for mobile-specific validation changes
2. Check insurance provider API response times on mobile
3. Consider temporarily hiding insurance step or making it optional

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 **STEP-BY-STEP BREAKDOWN**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Welcome & Eligibility
✅ Entries: 1,247 | Exits: 89 (7.1%) | ↑ 2.3% vs yesterday

Step 2: Basic Information
✅ Entries: 1,158 | Exits: 162 (14.0%) | ↓ 1.2% vs yesterday

Step 3: Medical History
✅ Entries: 996 | Exits: 179 (18.0%) | ↑ 0.8% vs yesterday

Step 4: Insurance Information
🚨 Entries: 817 | Exits: 253 (31.0%) | ↑ 13% vs yesterday
   **CRITICAL ISSUE** - Investigate immediately

Step 5: Treatment Preferences
✅ Entries: 564 | Exits: 98 (17.4%) | ↓ 0.5% vs yesterday

Step 6: Review & Submit
✅ Entries: 466 | Exits: 174 (37.3%) | ↑ 1.1% vs yesterday
   Note: Normal for final step

Completions: 292

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 **QUICK LINKS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

• [View Full Dashboard](https://dashboard.example.com)
• [Analyze Step 4](https://dashboard.example.com/funnel/main-wl?step=4)
• [Recent Deploys](https://vercel.com/deployments)
```

---

### 4. AI-Powered Test Recommendations

#### Data Inputs for AI Analysis
- Historical conversion rates by step (30-90 days)
- Drop-off patterns and trends
- Device/browser breakdown
- Time-on-step metrics
- Error logs and validation failures
- Previous A/B test results (if available)
- Industry benchmarks for telemedicine funnels

#### Recommendation Format

```typescript
interface TestRecommendation {
  id: string;
  priority: 'high' | 'medium' | 'low';
  testType: 'copy' | 'design' | 'flow' | 'validation' | 'timing';
  
  // Test Details
  title: string;
  hypothesis: string;
  targetStep: number;
  targetStepName: string;
  
  // Proposed Changes
  controlDescription: string;
  variantDescription: string;
  
  // Expected Impact
  estimatedImpact: {
    metric: 'conversion_rate' | 'drop_off_rate' | 'time_on_step';
    currentValue: number;
    expectedValue: number;
    percentageImprovement: number;
    confidence: 'high' | 'medium' | 'low';
  };
  
  // Supporting Data
  dataInsights: string[];
  similarTests: string[]; // References to similar successful tests
  
  // Implementation
  implementationComplexity: 'low' | 'medium' | 'high';
  estimatedEffort: string; // e.g., "2-4 hours"
  requiredTools: string[]; // e.g., ["Webflow", "Convert Insights"]
}
```

#### Example AI Prompt for Test Generation

```
You are a CRO expert specializing in telemedicine quiz funnels. Analyze the following funnel data and generate 3 high-impact A/B test recommendations.

Context:
- Company: Get Thin MD (telemedicine weight loss, hair loss, skincare)
- Funnel: Main Weight Loss Questionnaire
- Industry: Healthcare/Telemedicine
- Regulatory: Must maintain medical accuracy and compliance

Funnel Data:
{funnelMetrics}

Historical Patterns:
{historicalData}

Recent Changes:
{recentDeployments}

Please generate 3 test recommendations ranked by expected impact. For each test:
1. Clearly state the hypothesis based on data patterns
2. Explain the proposed change
3. Estimate the impact with supporting reasoning
4. Consider regulatory/compliance constraints
5. Provide implementation guidance

Focus on:
- High-friction steps with >25% drop-off
- Steps showing recent performance degradation
- Opportunities for progressive disclosure
- Mobile-specific optimizations
- Trust-building elements in healthcare context
```

#### Slack Recommendations Format

```
💡 **Weekly A/B Test Recommendations** - Week of Jan 15, 2025

Based on analysis of 7,342 funnel sessions this week, here are your top 3 testing opportunities:

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥇 **HIGH PRIORITY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Test #1: Simplify BMI Input (Step 3)**

**Hypothesis**: Reducing cognitive load by pre-calculating BMI will decrease drop-off

**Current State** (Control):
Users manually enter height and weight, then see calculated BMI and wait for eligibility check

**Proposed Change** (Variant):
Remove BMI calculation display, show immediate eligibility with friendly messaging: "Great! You may qualify for treatment"

**Data Supporting This**:
• 31% of users spend >45 seconds on this step (2x longer than average)
• 24% of drop-offs occur within 10 seconds of seeing BMI number
• Mobile users show 38% higher drop-off vs desktop at this step

**Expected Impact**:
• Step conversion: 71% → 79% (+8 percentage points)
• Overall funnel conversion: 23% → 25% (+2 percentage points)
• Est. additional conversions: ~30-40 per week
• Confidence: HIGH (similar test in hair loss funnel improved by 9%)

**Implementation**:
• Complexity: LOW
• Effort: 2-3 hours
• Tools: Webflow + Convert Insights
• Notes: Ensure BMI validation logic remains accurate in backend

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥈 **MEDIUM PRIORITY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Test #2: Add Trust Badge to Insurance Step (Step 4)**

**Hypothesis**: Adding HIPAA compliance badge will reduce privacy concerns and increase completion

**Current State**: Plain form asking for insurance details

**Proposed Change**: Add "🔒 HIPAA Compliant - Your Information is Secure" badge above form

**Data Supporting This**:
• 31% drop-off at insurance step (highest in funnel)
• Heatmap shows users hovering over "Why do you need this?" tooltip
• Similar healthcare funnels see 12-18% improvement with trust signals

**Expected Impact**:
• Step conversion: 69% → 76% (+7 percentage points)
• Overall funnel conversion: 23% → 24.5% (+1.5 percentage points)
• Confidence: MEDIUM (no previous test data for this specific change)

**Implementation**:
• Complexity: LOW
• Effort: 1-2 hours
• Tools: Webflow (add badge element)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥉 **TEST & LEARN**
━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Test #3: Progress Bar Enhancement (All Steps)**

**Hypothesis**: More granular progress indication will reduce perceived funnel length

**Current State**: 6-step progress bar (one indicator per step)

**Proposed Change**: 12-step micro-progress bar showing sub-steps within each main step

**Data Supporting This**:
• Average time-to-complete: 8 minutes 47 seconds
• 43% of drop-offs occur after Step 3 (halfway point)
• Users who complete Step 4 have 78% likelihood of finishing

**Expected Impact**:
• Overall funnel conversion: 23% → 24% (+1 percentage point)
• Confidence: LOW-MEDIUM (psychological effect, hard to predict)

**Implementation**:
• Complexity: MEDIUM
• Effort: 4-6 hours
• Tools: Webflow + custom JavaScript

🔗 **[View Full Analysis](https://dashboard.example.com/recommendations)**
```

---

### 5. Visual Analysis (Apify Integration) - Phase 2

#### Screenshot Capture

**Frequency**:
- Capture all funnel steps daily at 12:00 PM EST
- Capture on-demand via dashboard trigger
- Capture automatically when alert is triggered

**Capture Specifications**:
- Desktop: 1920x1080 resolution
- Mobile: iPhone 14 Pro (390x844) and Android (412x915)
- Full page screenshots with scroll capture
- Save with metadata: timestamp, device type, funnel ID, step number

**Storage**:
- Store in S3 or equivalent cloud storage
- Organize by date: `/screenshots/{funnelId}/{date}/{device}/{step}.png`
- Maintain 90-day rolling history
- Reference URLs stored in database

#### Visual Analysis Features

**Automated Visual Diffing**:
- Compare current screenshot to previous day
- Highlight pixel differences
- Flag significant layout changes (>5% of screen area)
- Alert on unexpected visual changes

**AI-Powered Content Analysis**:
Using Claude API with vision capabilities:
- Analyze form complexity (number of fields, layout density)
- Evaluate visual hierarchy and clarity
- Assess trust signals and credibility indicators
- Check mobile responsiveness and touch target sizes
- Identify potentially confusing UI elements

**Change Detection**:
- Track form field changes (added/removed fields)
- Monitor copy changes in CTAs, headlines, helper text
- Detect design system inconsistencies
- Flag potential accessibility issues

#### Analysis Prompt Template

```
You are analyzing a screenshot of a medical questionnaire step for a telemedicine company.

Context:
- Step: {stepNumber} - {stepName}
- Current drop-off rate: {dropOffRate}%
- Previous drop-off rate: {previousDropOffRate}%
- Device: {deviceType}

Tasks:
1. Identify potential UX issues that could cause drop-offs
2. Assess form complexity and cognitive load
3. Evaluate trust signals and credibility elements
4. Check mobile usability (if mobile screenshot)
5. Suggest specific improvements with rationale

Focus areas:
- Form field clarity and labels
- Visual hierarchy and attention flow
- Call-to-action effectiveness
- Error messaging and validation
- Loading states and progress indicators
- Trust signals (HIPAA, security, testimonials)

Provide actionable recommendations with priority levels.
```

---

## Data Models

### Database Schema

#### Funnels Table
```sql
CREATE TABLE funnels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  embeddables_id VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  total_steps INTEGER NOT NULL,
  status VARCHAR(50) DEFAULT 'active', -- active, paused, archived
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB -- store additional funnel configuration
);
```

#### Funnel Steps Table
```sql
CREATE TABLE funnel_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  step_number INTEGER NOT NULL,
  step_name VARCHAR(255) NOT NULL,
  step_type VARCHAR(100), -- e.g., form, info, confirmation
  fields JSONB, -- array of form fields if applicable
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(funnel_id, step_number)
);
```

#### Analytics Data Table
```sql
CREATE TABLE funnel_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  step_number INTEGER NOT NULL,
  date DATE NOT NULL,
  hour INTEGER, -- for hourly granularity (0-23), NULL for daily aggregates
  
  -- Metrics
  entries INTEGER DEFAULT 0,
  exits INTEGER DEFAULT 0,
  conversions INTEGER DEFAULT 0, -- continued to next step
  drop_off_rate DECIMAL(5,2), -- calculated: exits / entries * 100
  conversion_rate DECIMAL(5,2), -- calculated: conversions / entries * 100
  
  -- Segmentation
  device_type VARCHAR(50), -- desktop, mobile, tablet, NULL for all devices
  browser VARCHAR(50), -- chrome, safari, firefox, NULL for all browsers
  
  -- Time metrics
  avg_time_on_step INTEGER, -- seconds
  median_time_on_step INTEGER,
  
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(funnel_id, step_number, date, hour, device_type, browser)
);

CREATE INDEX idx_analytics_funnel_date ON funnel_analytics(funnel_id, date DESC);
CREATE INDEX idx_analytics_step_date ON funnel_analytics(funnel_id, step_number, date DESC);
```

#### Alerts Table
```sql
CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  step_number INTEGER,
  
  severity VARCHAR(20) NOT NULL, -- critical, warning, info
  type VARCHAR(50) NOT NULL, -- drop_off, conversion, volume, step_anomaly
  
  -- Metrics
  current_value DECIMAL(10,2) NOT NULL,
  previous_day_value DECIMAL(10,2),
  seven_day_average DECIMAL(10,2),
  percentage_change DECIMAL(10,2),
  
  -- Context
  message TEXT NOT NULL,
  recommendation TEXT,
  
  -- Status
  status VARCHAR(20) DEFAULT 'active', -- active, acknowledged, resolved
  acknowledged_by VARCHAR(255),
  acknowledged_at TIMESTAMP,
  resolved_at TIMESTAMP,
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alerts_status ON alerts(status) WHERE status = 'active';
CREATE INDEX idx_alerts_funnel ON alerts(funnel_id, created_at DESC);
```

#### Daily Reports Table
```sql
CREATE TABLE daily_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  report_date DATE NOT NULL,
  
  -- Summary metrics
  total_starts INTEGER,
  total_completions INTEGER,
  overall_conversion_rate DECIMAL(5,2),
  
  -- AI Analysis
  ai_summary TEXT, -- Executive summary from Claude
  main_blockers JSONB, -- Array of identified blockers
  insights JSONB, -- Array of insights and patterns
  
  -- Step-by-step data
  step_data JSONB, -- Detailed metrics for each step
  
  -- Metadata
  sent_to_slack BOOLEAN DEFAULT FALSE,
  slack_timestamp VARCHAR(50),
  
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(funnel_id, report_date)
);

CREATE INDEX idx_reports_date ON daily_reports(report_date DESC);
```

#### Test Recommendations Table
```sql
CREATE TABLE test_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  
  -- Test details
  title VARCHAR(255) NOT NULL,
  hypothesis TEXT NOT NULL,
  priority VARCHAR(20), -- high, medium, low
  test_type VARCHAR(50), -- copy, design, flow, validation, timing
  target_step INTEGER,
  
  -- Expected impact
  estimated_impact JSONB, -- {metric, currentValue, expectedValue, improvement, confidence}
  
  -- Implementation
  control_description TEXT,
  variant_description TEXT,
  implementation_complexity VARCHAR(20), -- low, medium, high
  estimated_effort VARCHAR(100),
  required_tools TEXT[],
  
  -- Supporting data
  data_insights JSONB, -- Array of insights supporting this test
  
  -- Status
  status VARCHAR(50) DEFAULT 'suggested', -- suggested, approved, in_progress, completed, rejected
  implemented_at TIMESTAMP,
  results JSONB, -- Store A/B test results if implemented
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recommendations_status ON test_recommendations(status, priority);
```

#### Screenshots Table (Phase 2)
```sql
CREATE TABLE screenshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  funnel_id UUID REFERENCES funnels(id) ON DELETE CASCADE,
  step_number INTEGER NOT NULL,
  
  -- Capture details
  captured_at TIMESTAMP NOT NULL,
  device_type VARCHAR(20) NOT NULL, -- desktop, mobile_ios, mobile_android
  resolution VARCHAR(20), -- e.g., 1920x1080
  
  -- Storage
  storage_url TEXT NOT NULL, -- S3 or cloud storage URL
  thumbnail_url TEXT,
  
  -- Analysis
  visual_diff_score DECIMAL(5,2), -- 0-100, percentage of pixels changed vs previous
  ai_analysis JSONB, -- Store Claude's analysis of the screenshot
  
  -- Metadata
  file_size INTEGER, -- bytes
  apify_run_id VARCHAR(255),
  
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_screenshots_funnel_step ON screenshots(funnel_id, step_number, captured_at DESC);
```

---

## API Endpoints

### Core Analytics Endpoints

#### GET /api/funnels
List all available funnels
```typescript
Response: {
  funnels: Array<{
    id: string;
    name: string;
    totalSteps: number;
    status: string;
    lastUpdated: string;
  }>;
}
```

#### GET /api/funnels/:funnelId
Get funnel details and current metrics
```typescript
Query params:
  - startDate: ISO date string
  - endDate: ISO date string
  - compareToStart?: ISO date string (for comparison mode)
  - compareToEnd?: ISO date string

Response: {
  funnel: FunnelDetails;
  metrics: {
    overall: {
      totalStarts: number;
      totalCompletions: number;
      conversionRate: number;
      comparison?: { /* vs previous period */ }
    };
    steps: Array<StepMetrics>;
  };
}
```

#### GET /api/funnels/:funnelId/steps/:stepNumber
Get detailed metrics for a specific step
```typescript
Query params:
  - startDate: ISO date string
  - endDate: ISO date string
  - segmentBy?: 'device' | 'browser' | 'hour' // optional segmentation

Response: {
  step: StepDetails;
  metrics: StepMetrics;
  trends: Array<{ date: string; value: number }>; // time series
  segments?: Record<string, StepMetrics>; // if segmentBy provided
}
```

#### GET /api/funnels/:funnelId/trends
Get historical trend data for charting
```typescript
Query params:
  - startDate: ISO date string
  - endDate: ISO date string
  - granularity: 'hour' | 'day' | 'week'
  - metric: 'conversion_rate' | 'drop_off_rate' | 'starts'

Response: {
  trends: Array<{
    timestamp: string;
    value: number;
    label: string;
  }>;
}
```

### Alert Endpoints

#### GET /api/alerts
Get all active alerts
```typescript
Query params:
  - status?: 'active' | 'acknowledged' | 'resolved'
  - severity?: 'critical' | 'warning' | 'info'
  - funnelId?: string

Response: {
  alerts: Array<Alert>;
  summary: {
    totalActive: number;
    critical: number;
    warnings: number;
  };
}
```

#### POST /api/alerts/:alertId/acknowledge
Acknowledge an alert
```typescript
Body: {
  acknowledgedBy: string; // user identifier
  note?: string;
}

Response: {
  alert: Alert; // updated alert with acknowledged status
}
```

#### POST /api/alerts/:alertId/resolve
Mark alert as resolved
```typescript
Body: {
  resolvedBy: string;
  resolution: string;
}

Response: {
  alert: Alert;
}
```

### Report Endpoints

#### GET /api/reports/daily/:date
Get daily report for a specific date
```typescript
Response: {
  report: DailyReport;
}
```

#### POST /api/reports/daily/generate
Manually trigger daily report generation
```typescript
Body: {
  date: string; // ISO date
  funnelId: string;
  sendToSlack?: boolean;
}

Response: {
  report: DailyReport;
  slackSent: boolean;
}
```

#### GET /api/reports/history
Get historical reports
```typescript
Query params:
  - funnelId: string
  - startDate: ISO date string
  - endDate: ISO date string

Response: {
  reports: Array<DailyReportSummary>;
}
```

### Recommendation Endpoints

#### GET /api/recommendations
Get current test recommendations
```typescript
Query params:
  - funnelId: string
  - status?: 'suggested' | 'approved' | 'in_progress'
  - priority?: 'high' | 'medium' | 'low'

Response: {
  recommendations: Array<TestRecommendation>;
}
```

#### POST /api/recommendations/generate
Generate new test recommendations using AI
```typescript
Body: {
  funnelId: string;
  daysOfData?: number; // default 30
  focusSteps?: number[]; // optional, specific steps to analyze
}

Response: {
  recommendations: Array<TestRecommendation>;
  generatedAt: string;
}
```

#### POST /api/recommendations/:id/status
Update recommendation status
```typescript
Body: {
  status: 'approved' | 'in_progress' | 'completed' | 'rejected';
  note?: string;
  results?: object; // if completed, store test results
}

Response: {
  recommendation: TestRecommendation;
}
```

---

## Integration Specifications

### Embeddables API Integration

#### Authentication
```typescript
// Store in environment variables
EMBEDDABLES_API_KEY=your_api_key_here
EMBEDDABLES_API_URL=https://api.embeddables.com/v1
```

#### Key Endpoints to Use

**List Forms/Quizzes**
```
GET /forms
Authorization: Bearer {API_KEY}

Response: {
  forms: Array<{
    id: string;
    name: string;
    steps: number;
    status: string;
  }>
}
```

**Get Form Analytics**
```
GET /forms/{formId}/analytics
Query params:
  - start_date: YYYY-MM-DD
  - end_date: YYYY-MM-DD
  - granularity: hour | day

Response: {
  form: FormDetails;
  analytics: {
    steps: Array<{
      stepId: string;
      stepName: string;
      stepNumber: number;
      entries: number;
      exits: number;
      avgTimeSpent: number;
    }>;
    sessions: {
      total: number;
      completed: number;
      abandoned: number;
    };
    devices: Record<string, number>;
    browsers: Record<string, number>;
  };
}
```

**Get Individual Submissions**
```
GET /forms/{formId}/submissions
Query params:
  - start_date: YYYY-MM-DD
  - end_date: YYYY-MM-DD
  - limit: number
  - offset: number

Response: {
  submissions: Array<{
    id: string;
    completedAt: string | null;
    stepsCompleted: number;
    totalSteps: number;
    device: string;
    browser: string;
    exitedAt: number | null; // step number where user exited
  }>;
  total: number;
}
```

#### Data Sync Strategy

**Scheduled Sync (Cron Job)**
- Run every 30 minutes during business hours (8 AM - 10 PM EST)
- Run every 2 hours during off-hours
- Fetch data for last 24 hours to catch any delayed events

**Data Processing**
```typescript
async function syncEmbeddablesData(funnelId: string) {
  // 1. Fetch raw data from Embeddables API
  const rawData = await embeddablesAPI.getAnalytics(funnelId, {
    start_date: getYesterday(),
    end_date: getToday(),
  });
  
  // 2. Transform to internal data model
  const transformedData = transformEmbeddablesData(rawData);
  
  // 3. Upsert into database
  await db.funnelAnalytics.upsertMany(transformedData);
  
  // 4. Calculate derived metrics
  await calculateDerivedMetrics(funnelId);
  
  // 5. Check for anomalies and trigger alerts
  await checkForAnomalies(funnelId);
  
  // 6. Update Redis cache
  await updateCache(funnelId);
}
```

### Slack Integration

#### Webhook Setup
```typescript
// Store in environment variables
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#funnel-alerts
SLACK_DAILY_REPORT_CHANNEL=#daily-reports
```

#### Send Alert to Slack
```typescript
async function sendAlertToSlack(alert: Alert) {
  const message = {
    blocks: [
      {
        type: "header",
        text: {
          type: "plain_text",
          text: `${getSeverityEmoji(alert.severity)} ${alert.type.toUpperCase()} ALERT`,
          emoji: true
        }
      },
      {
        type: "section",
        fields: [
          {
            type: "mrkdwn",
            text: `*Funnel:*\n${alert.funnelName}`
          },
          {
            type: "mrkdwn",
            text: `*Step:*\nStep ${alert.stepNumber} - ${alert.stepName}`
          }
        ]
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: alert.message
        }
      },
      {
        type: "section",
        fields: [
          {
            type: "mrkdwn",
            text: `*Current:* ${alert.currentValue}%`
          },
          {
            type: "mrkdwn",
            text: `*Previous:* ${alert.previousDayValue}%`
          },
          {
            type: "mrkdwn",
            text: `*7-day Avg:* ${alert.sevenDayAverage}%`
          },
          {
            type: "mrkdwn",
            text: `*Change:* ${alert.percentageChange > 0 ? '+' : ''}${alert.percentageChange}%`
          }
        ]
      },
      {
        type: "actions",
        elements: [
          {
            type: "button",
            text: {
              type: "plain_text",
              text: "View Dashboard",
              emoji: true
            },
            url: `${process.env.DASHBOARD_URL}/funnel/${alert.funnelId}?step=${alert.stepNumber}`,
            action_id: "view_dashboard"
          },
          {
            type: "button",
            text: {
              type: "plain_text",
              text: "Acknowledge",
              emoji: true
            },
            url: `${process.env.DASHBOARD_URL}/alerts/${alert.id}`,
            action_id: "acknowledge_alert"
          }
        ]
      }
    ]
  };
  
  await fetch(process.env.SLACK_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message)
  });
}
```

#### Daily Report Formatting
Similar structure using Slack Block Kit with rich formatting, tables, and action buttons.

### Apify Integration (Phase 2)

#### Screenshot Capture Actor
```typescript
// Apify API setup
APIFY_API_TOKEN=your_apify_token
APIFY_ACTOR_ID=apify/web-scraper // or custom screenshot actor

// Trigger screenshot capture
async function captureScreenshots(funnelId: string, stepUrls: string[]) {
  const run = await apifyClient.actor(APIFY_ACTOR_ID).call({
    startUrls: stepUrls.map(url => ({ url })),
    screenshots: true,
    screenshotFormat: 'png',
    viewportWidth: [1920, 390, 412], // desktop, iOS, Android
    waitForSelector: '.quiz-container', // ensure page is fully loaded
    maxConcurrency: 3,
  });
  
  // Download screenshots from Apify dataset
  const dataset = await apifyClient.dataset(run.defaultDatasetId).listItems();
  
  // Upload to S3 and save metadata
  for (const item of dataset.items) {
    const s3Url = await uploadToS3(item.screenshot, {
      bucket: 'funnel-screenshots',
      key: `${funnelId}/${new Date().toISOString()}/${item.device}/${item.stepNumber}.png`
    });
    
    await db.screenshots.create({
      funnelId,
      stepNumber: item.stepNumber,
      deviceType: item.device,
      storageUrl: s3Url,
      capturedAt: new Date(),
    });
  }
  
  return run.id;
}
```

#### Claude Vision Analysis
```typescript
async function analyzeScreenshot(screenshotId: string) {
  const screenshot = await db.screenshots.findById(screenshotId);
  const stepMetrics = await db.funnelAnalytics.getLatestForStep(
    screenshot.funnelId,
    screenshot.stepNumber
  );
  
  // Download screenshot from S3
  const imageBuffer = await downloadFromS3(screenshot.storageUrl);
  const base64Image = imageBuffer.toString('base64');
  
  // Call Claude API with vision
  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4',
    max_tokens: 2000,
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'image',
            source: {
              type: 'base64',
              media_type: 'image/png',
              data: base64Image,
            },
          },
          {
            type: 'text',
            text: `Analyze this screenshot of Step ${screenshot.stepNumber} from a telemedicine quiz funnel. Current drop-off rate: ${stepMetrics.dropOffRate}%. Identify UX issues and suggest improvements.`
          },
        ],
      },
    ],
  });
  
  // Store analysis
  await db.screenshots.update(screenshotId, {
    ai_analysis: {
      content: response.content,
      timestamp: new Date(),
    },
  });
  
  return response.content;
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Basic analytics dashboard with Embeddables integration

**Deliverables**:
- Database schema setup (PostgreSQL)
- Embeddables API integration (data fetching and sync)
- Basic Next.js dashboard structure
- Funnel overview page with key metrics
- Step-by-step breakdown table
- Date range selector

**Success Criteria**:
- Can view funnel data for any date range
- Data syncs from Embeddables every 30 minutes
- Dashboard loads in <2 seconds

### Phase 2: Alerting (Week 2-3)
**Goal**: Real-time anomaly detection and Slack notifications

**Deliverables**:
- Alert detection logic (comparing current vs baselines)
- Alert management system (acknowledge, resolve)
- Slack webhook integration for alerts
- Alerts dashboard page
- Background job for continuous monitoring

**Success Criteria**:
- Alerts trigger within 15 minutes of anomaly
- Zero false positives in first week
- Slack messages formatted correctly with action buttons

### Phase 3: Daily Reports (Week 3-4)
**Goal**: Automated AI-powered daily analysis

**Deliverables**:
- Claude API integration for analysis
- Daily report generation logic
- Cron job scheduled for 8 AM EST
- Slack daily report formatting
- Report history page

**Success Criteria**:
- Report delivers on time every day
- AI insights are actionable and specific
- Report includes clear blockers and recommendations

### Phase 4: AI Recommendations (Week 4-5)
**Goal**: Generate data-driven A/B test ideas

**Deliverables**:
- Test recommendation generation using Claude
- Recommendation management system
- Weekly recommendation schedule
- Recommendation dashboard page
- Slack notifications for new recommendations

**Success Criteria**:
- 3 quality recommendations generated weekly
- Recommendations are specific and implementable
- Team can approve/reject and track status

### Phase 5: Visual Analysis (Week 6-7)
**Goal**: Screenshot capture and visual QA

**Deliverables**:
- Apify integration for screenshot capture
- Screenshot storage and management
- Visual diff detection
- Claude vision API integration for analysis
- Screenshot gallery in dashboard

**Success Criteria**:
- Daily screenshots captured reliably
- Visual changes detected accurately
- AI analysis provides actionable UX insights

### Phase 6: Polish & Optimization (Week 8)
**Goal**: Performance, UX improvements, documentation

**Deliverables**:
- Performance optimization (caching, query optimization)
- Mobile-responsive dashboard
- User documentation
- Admin settings page
- Export functionality (CSV, PDF reports)

**Success Criteria**:
- Dashboard fully usable on mobile
- All pages load in <1 second (cached)
- Complete documentation for setup and usage

---

## Environment Variables

Create a `.env.local` file with the following:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/funnel_analytics
REDIS_URL=redis://localhost:6379

# Embeddables API
EMBEDDABLES_API_KEY=your_embeddables_api_key
EMBEDDABLES_API_URL=https://api.embeddables.com/v1

# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_ALERTS_CHANNEL=#funnel-alerts
SLACK_REPORTS_CHANNEL=#daily-reports

# Claude API (Anthropic)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Apify (Phase 2)
APIFY_API_TOKEN=your_apify_token
APIFY_SCREENSHOT_ACTOR_ID=apify/web-scraper

# S3 Storage (Phase 2)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_S3_BUCKET=funnel-screenshots
AWS_REGION=us-east-1

# Application
NEXT_PUBLIC_DASHBOARD_URL=http://localhost:3000
NODE_ENV=development
CRON_SECRET=random_secret_for_vercel_cron
```

---

## Development Setup

### Prerequisites
- Node.js 18+ and npm/pnpm
- PostgreSQL 14+
- Redis 6+
- Embeddables API credentials

### Initial Setup

```bash
# 1. Create new Next.js project
npx create-next-app@latest funnel-analytics --typescript --tailwind --app

# 2. Install dependencies
cd funnel-analytics
npm install @anthropic-ai/sdk
npm install @slack/webhook
npm install postgres
npm install ioredis
npm install recharts
npm install date-fns
npm install zod
npm install @radix-ui/react-select @radix-ui/react-dialog
npm install lucide-react

# 3. Set up database
createdb funnel_analytics
npm install -D prisma
npx prisma init
# Copy database schema to prisma/schema.prisma
npx prisma migrate dev --name init

# 4. Create .env.local with your credentials

# 5. Run development server
npm run dev
```

### Project Structure

```
funnel-analytics/
├── app/
│   ├── api/
│   │   ├── funnels/
│   │   │   ├── route.ts                    # List funnels
│   │   │   └── [id]/
│   │   │       ├── route.ts                # Get funnel details
│   │   │       ├── steps/
│   │   │       │   └── [stepNumber]/route.ts
│   │   │       └── trends/route.ts
│   │   ├── alerts/
│   │   │   ├── route.ts                    # List/create alerts
│   │   │   └── [id]/
│   │   │       ├── acknowledge/route.ts
│   │   │       └── resolve/route.ts
│   │   ├── reports/
│   │   │   ├── daily/
│   │   │   │   ├── [date]/route.ts
│   │   │   │   └── generate/route.ts
│   │   │   └── history/route.ts
│   │   ├── recommendations/
│   │   │   ├── route.ts
│   │   │   ├── generate/route.ts
│   │   │   └── [id]/status/route.ts
│   │   └── cron/
│   │       ├── sync-data/route.ts          # Embeddables sync
│   │       ├── check-alerts/route.ts       # Alert monitoring
│   │       └── daily-report/route.ts       # Report generation
│   ├── dashboard/
│   │   ├── page.tsx                        # Main dashboard
│   │   ├── [funnelId]/
│   │   │   ├── page.tsx                    # Funnel details
│   │   │   └── steps/[stepNumber]/page.tsx
│   │   ├── alerts/page.tsx
│   │   ├── reports/page.tsx
│   │   └── recommendations/page.tsx
│   ├── layout.tsx
│   └── page.tsx                            # Landing/login
├── components/
│   ├── ui/                                 # Shadcn components
│   ├── charts/
│   │   ├── FunnelChart.tsx
│   │   ├── TrendChart.tsx
│   │   └── HeatmapChart.tsx
│   ├── dashboard/
│   │   ├── MetricsCard.tsx
│   │   ├── DateRangePicker.tsx
│   │   ├── FunnelSelector.tsx
│   │   └── StepBreakdown.tsx
│   └── alerts/
│       ├── AlertCard.tsx
│       └── AlertList.tsx
├── lib/
│   ├── db/
│   │   ├── prisma.ts
│   │   └── queries/
│   │       ├── funnels.ts
│   │       ├── analytics.ts
│   │       └── alerts.ts
│   ├── integrations/
│   │   ├── embeddables.ts
│   │   ├── slack.ts
│   │   ├── anthropic.ts
│   │   └── apify.ts
│   ├── services/
│   │   ├── alert-detection.ts
│   │   ├── report-generator.ts
│   │   └── recommendation-engine.ts
│   ├── utils/
│   │   ├── calculations.ts
│   │   └── formatters.ts
│   └── cache.ts                            # Redis wrapper
├── types/
│   ├── funnel.ts
│   ├── alert.ts
│   └── recommendation.ts
├── prisma/
│   └── schema.prisma
├── public/
├── .env.local
├── next.config.js
├── package.json
└── tsconfig.json
```

---

## Testing Strategy

### Unit Tests
- Calculation functions (conversion rates, drop-offs, trends)
- Data transformation logic
- Alert detection algorithms

### Integration Tests
- Embeddables API integration
- Database queries and transactions
- Slack webhook delivery

### End-to-End Tests
- Dashboard page loads and displays data
- Alert triggering and acknowledgment flow
- Report generation and Slack delivery

### Performance Tests
- Dashboard load time with large datasets
- API response times under load
- Database query optimization

---

## Monitoring & Observability

### Application Monitoring
- Track API response times
- Monitor cron job execution success/failure
- Track Embeddables API rate limits and errors
- Monitor database connection pool

### Business Metrics
- Alert accuracy (false positive rate)
- Daily report delivery success rate
- User engagement with dashboard
- Time-to-resolution for critical alerts

### Error Tracking
- Sentry or similar for error monitoring
- Slack notifications for critical errors
- Weekly error summary report

---

## Security Considerations

### API Security
- Rate limiting on all public endpoints
- API key rotation policy
- Input validation on all user inputs
- SQL injection prevention (use parameterized queries)

### Data Privacy
- No PII stored (only aggregate metrics)
- Secure storage of API credentials
- Access control for dashboard (authentication)
- Audit logging for sensitive operations

### Compliance
- HIPAA compliance considerations (no patient data in system)
- Data retention policies (90 days for screenshots, 1 year for analytics)
- Secure communication (HTTPS only)

---

## Scaling Considerations

### Database Optimization
- Partition analytics table by date
- Create appropriate indexes for common queries
- Archive historical data beyond retention period
- Consider TimescaleDB for time-series data

### Caching Strategy
- Redis for frequently accessed metrics
- Browser caching for static dashboard assets
- CDN for screenshots and images
- Cache invalidation on data updates

### High Volume Handling
- Queue system for alert processing (Bull or similar)
- Batch processing for Embeddables data sync
- Horizontal scaling for API servers
- Read replicas for database if needed

---

## Future Enhancements

### Advanced Analytics
- Cohort analysis (compare user segments)
- Predictive analytics (forecast conversion rates)
- Multivariate testing support
- Attribution modeling

### Enhanced AI Features
- Natural language querying ("Show me why conversion dropped last Tuesday")
- Automated A/B test result analysis
- Personalized recommendations based on funnel type
- Anomaly explanation with root cause analysis

### Integration Expansions
- Google Analytics integration
- Segment integration for event tracking
- Mixpanel or Amplitude integration
- Zapier integration for custom workflows

### Team Collaboration
- User roles and permissions
- Commenting on alerts and reports
- Shared dashboards and custom views
- Team notifications and mentions

---

## Success Criteria Summary

### Metrics to Track
- **Time to detect issues**: Target <15 minutes
- **Alert accuracy**: Target >90% (low false positive rate)
- **Daily report delivery**: Target 100% on-time delivery
- **Dashboard performance**: Target <2s load time
- **AI recommendation quality**: Target >70% approval rate from team

### Business Impact
- Reduce funnel optimization cycle time by 50%
- Increase overall conversion rate by 10-20% through faster iteration
- Save 5-10 hours per week in manual data analysis
- Improve cross-team visibility into funnel performance

---

## Support & Maintenance

### Regular Maintenance Tasks
- Weekly review of alert thresholds (adjust for false positives)
- Monthly review of AI prompt effectiveness
- Quarterly review of dashboard UX and features
- Regular dependency updates

### Documentation
- API documentation (OpenAPI/Swagger)
- User guide for dashboard features
- Runbook for common issues
- Architecture decision records (ADRs)

### Feedback Loop
- Weekly team feedback sessions
- Track feature requests in backlog
- Monitor dashboard usage analytics
- Iterate based on user needs

---

## Questions for Claude Code

When implementing this system, Claude Code should consider:

1. **Embeddables API**: What is the exact structure of their analytics API? We may need to explore their documentation.

2. **Alert Thresholds**: What are appropriate thresholds for different alert types? Should they be configurable?

3. **AI Prompt Engineering**: How should we structure prompts to Claude API for best results in report generation and recommendations?

4. **Scalability**: What is the expected data volume? How many funnels, steps, and daily sessions?

5. **Infrastructure**: Should we deploy on Vercel, or would a different platform be better suited?

6. **Authentication**: What authentication method should we use for the dashboard? (Auth0, Clerk, Next-Auth?)

---

## Conclusion

This system will provide comprehensive visibility into quiz funnel performance with AI-powered insights and proactive monitoring. By automating data analysis and alerting, it will enable the team to identify and resolve issues faster, leading to improved conversion rates and better patient experiences.

The phased approach allows for iterative development with regular feedback, ensuring the system meets actual needs while maintaining high code quality and performance standards.
