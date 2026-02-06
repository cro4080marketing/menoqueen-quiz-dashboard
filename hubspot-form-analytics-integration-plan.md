# HubSpot Form Analytics Integration - Project Plan

## Project Overview

**Objective**: Build a comprehensive integration to extract and analyze HubSpot form analytics data, enabling granular reporting by page, form, field, and time period.

**Client**: Acquisition.com (Client Start Implementation)

**Scope**: Pull all available form analytics insights from HubSpot's API to enable drill-down analysis across forms, pages, submissions, and performance metrics.

---

## Executive Summary

HubSpot provides extensive form analytics through its API, including submission data, performance metrics, field-level analytics, and conversion tracking. This integration will create a data pipeline to systematically extract, transform, and present this data for analysis.

**Key Capabilities to Build**:
- Form submission tracking and analysis
- Page-level form performance
- Field-level completion rates and drop-off analysis
- Time-series performance tracking
- Form conversion funnel analysis
- Multi-form comparison and benchmarking

---

## HubSpot API Capabilities

### Available Analytics Endpoints

#### 1. Forms API (v3)
**Endpoint**: `/marketing/v3/forms`
- List all forms in portal
- Get individual form details
- Form configuration and field structure
- Form metadata (creation date, last updated, etc.)

#### 2. Form Submissions API (v3)
**Endpoint**: `/form-integrations/v1/submissions/forms/{formGuid}`
- Individual submission data
- Submission timestamps
- Field values submitted
- Page context (URL where form was submitted)
- Contact associations

#### 3. Analytics API (v2)
**Endpoint**: `/analytics/v2/reports`
- Form views
- Form submissions
- Conversion rates
- Time-based aggregations

#### 4. CRM Objects (Contacts)
**Endpoint**: `/crm/v3/objects/contacts`
- Contact creation source (form submissions)
- Form-to-contact attribution
- Lifecycle stage progression from form fills

### Data Points Available

**Form-Level Metrics**:
- Total submissions (all-time and by date range)
- Unique views
- Conversion rate (submissions/views)
- Form fields and structure
- Form name, GUID, portal ID
- Creation and modification dates
- Form type (embedded, standalone, pop-up)
- Active/inactive status

**Submission-Level Data**:
- Submission timestamp (precise to the second)
- IP address
- Page URL where submitted
- Page title
- Referrer URL
- User agent
- Cookie tracking data (HubSpot tracking cookie)
- All field values submitted
- Contact GUID (if available)

**Page-Level Analytics**:
- Forms present on each page
- Page URL performance
- Submissions by landing page
- Multi-step form tracking

**Field-Level Insights**:
- Field completion rates
- Field abandonment patterns
- Required vs optional field performance
- Field validation errors (if tracked)

---

## Authentication & Setup Requirements

### 1. HubSpot Private App Access Token
**Required Scopes**:
- `forms` (read forms)
- `analytics.read` (read analytics data)
- `crm.objects.contacts.read` (read contact records)
- `oauth` (if using OAuth flow)

**Setup Steps**:
1. Navigate to HubSpot Settings → Integrations → Private Apps
2. Create new private app
3. Enable required scopes
4. Generate access token
5. Store token securely (environment variable or secrets manager)

### 2. Rate Limits
- **Burst limit**: 100 requests per 10 seconds
- **Daily limit**: 500,000 requests per day (varies by subscription tier)
- **Recommendation**: Implement exponential backoff and request queuing

### 3. Portal ID
- Obtain from HubSpot account settings
- Required for certain API endpoints

---

## Data Schema & Structure

### Form Object
```json
{
  "id": "form_guid_here",
  "name": "Contact Us Form",
  "portalId": 12345678,
  "guid": "abc-123-def-456",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-12-01T14:20:00Z",
  "formType": "HUBSPOT",
  "fieldGroups": [
    {
      "groupType": "default_group",
      "richTextType": "text",
      "fields": [
        {
          "name": "email",
          "label": "Email",
          "type": "string",
          "fieldType": "text",
          "required": true,
          "hidden": false,
          "validation": {
            "data": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
          }
        }
      ]
    }
  ],
  "submitText": "Submit",
  "deletable": true,
  "captchaEnabled": false,
  "cssClass": "",
  "followUpId": "",
  "inlineMessage": "Thanks for submitting the form.",
  "themeName": "default"
}
```

### Submission Object
```json
{
  "submittedAt": 1704452400000,
  "values": [
    {
      "name": "email",
      "value": "user@example.com"
    },
    {
      "name": "firstname",
      "value": "John"
    }
  ],
  "pageUrl": "https://example.com/contact",
  "pageTitle": "Contact Us",
  "ipAddress": "192.168.1.1",
  "hutk": "hubspot_tracking_cookie_value",
  "pageName": "contact"
}
```

### Analytics Aggregation Schema (Proposed Output)
```json
{
  "formId": "form_guid",
  "formName": "Contact Us Form",
  "dateRange": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "metrics": {
    "totalViews": 1250,
    "totalSubmissions": 187,
    "conversionRate": 14.96,
    "uniqueSubmissions": 182,
    "duplicateSubmissions": 5
  },
  "pageBreakdown": [
    {
      "pageUrl": "https://example.com/contact",
      "views": 850,
      "submissions": 145,
      "conversionRate": 17.06
    },
    {
      "pageUrl": "https://example.com/about",
      "views": 400,
      "submissions": 42,
      "conversionRate": 10.5
    }
  ],
  "fieldAnalytics": [
    {
      "fieldName": "email",
      "required": true,
      "completionRate": 100,
      "validationErrors": 12
    },
    {
      "fieldName": "phone",
      "required": false,
      "completionRate": 67.3,
      "validationErrors": 3
    }
  ],
  "timeSeries": [
    {
      "date": "2024-01-01",
      "views": 42,
      "submissions": 6,
      "conversionRate": 14.29
    }
  ]
}
```

---

## Implementation Phases

### Phase 1: Foundation & Data Collection (Week 1)

**Goal**: Establish API connectivity and retrieve raw data

**Tasks**:
1. Set up project structure and dependencies
   - Python (recommended: `requests`, `pandas`, `python-dotenv`)
   - Or Node.js (`axios`, `dotenv`, `date-fns`)
   
2. Implement authentication
   - Create `.env` file for API token storage
   - Build authentication headers
   - Test API connectivity

3. Build core data fetchers
   - `fetch_all_forms()` - Retrieve all forms from portal
   - `fetch_form_details(form_id)` - Get specific form configuration
   - `fetch_form_submissions(form_id, start_date, end_date)` - Get submissions
   - Implement pagination handling (HubSpot uses `after` cursor)

4. Create data storage layer
   - Design database schema (SQLite for local, PostgreSQL for production)
   - Or use file-based storage (JSON/CSV) for simple implementation
   - Tables: `forms`, `submissions`, `fields`, `analytics_daily`

5. Error handling & logging
   - Rate limit detection and backoff
   - API error handling (400, 401, 403, 429, 500 errors)
   - Logging framework setup

**Deliverables**:
- Working API client
- Data fetching modules
- Basic error handling
- Sample data retrieval test

---

### Phase 2: Data Processing & Analytics Engine (Week 2)

**Goal**: Transform raw data into actionable analytics

**Tasks**:
1. Build aggregation functions
   - Calculate form-level metrics (views, submissions, conversion rates)
   - Aggregate by time period (daily, weekly, monthly)
   - Page-level performance calculations
   - Field-level completion analysis

2. Create data transformation pipeline
   - Clean and normalize submission data
   - Extract UTM parameters from page URLs
   - Parse referrer data for traffic source attribution
   - Handle missing or malformed data

3. Implement comparison logic
   - Form-to-form performance comparison
   - Time period comparisons (month-over-month, year-over-year)
   - Benchmark calculations

4. Field analytics processor
   - Calculate field completion rates
   - Identify field drop-off patterns
   - Analyze optional vs required field performance
   - Flag high-friction fields

**Deliverables**:
- Data transformation pipeline
- Analytics calculation engine
- Comparison and benchmark logic
- Field performance analyzer

---

### Phase 3: Reporting & Visualization (Week 3)

**Goal**: Create user-facing reports and dashboards

**Tasks**:
1. Design report templates
   - Executive summary dashboard
   - Form-specific deep dive
   - Page performance report
   - Field optimization report
   - Time-series trend analysis

2. Build report generation engine
   - HTML report generator (optional: PDF export)
   - CSV exports for each report type
   - JSON API endpoints (if building web interface)

3. Create visualization components
   - Conversion funnel charts
   - Time-series line graphs
   - Page performance bar charts
   - Field completion heatmaps
   - Top/bottom performer tables

4. Implement filtering and drill-down
   - Date range selection
   - Form filtering
   - Page URL filtering
   - Field-level filtering

**Deliverables**:
- Report templates
- Visualization library
- Export functionality
- Interactive filtering

---

### Phase 4: Automation & Scheduling (Week 4)

**Goal**: Automate data collection and reporting

**Tasks**:
1. Build scheduling system
   - Daily data sync job
   - Weekly report generation
   - Monthly summary reports
   - Ad-hoc on-demand reporting

2. Create notification system
   - Email reports (using SendGrid, AWS SES, or SMTP)
   - Slack notifications for anomalies
   - Alert thresholds (e.g., conversion rate drops >20%)

3. Implement incremental updates
   - Only fetch new submissions since last sync
   - Update existing form configurations
   - Efficient delta processing

4. Add data validation
   - Submission data quality checks
   - Duplicate detection
   - Anomaly detection (unusual spike/drop in submissions)

**Deliverables**:
- Automated scheduling system
- Notification framework
- Incremental sync logic
- Data validation rules

---

## Technical Architecture

### Recommended Tech Stack

**Option 1: Python-Based**
```
- Language: Python 3.9+
- API Client: requests or httpx
- Data Processing: pandas, numpy
- Database: SQLite (dev) / PostgreSQL (prod)
- Scheduling: APScheduler or Celery
- Visualization: matplotlib, plotly, or Chart.js (for web)
- Reporting: Jinja2 templates, weasyprint (PDF)
```

**Option 2: Node.js-Based**
```
- Language: Node.js 16+
- API Client: axios or node-fetch
- Data Processing: lodash, date-fns
- Database: SQLite (better-sqlite3) / PostgreSQL (pg)
- Scheduling: node-cron or Bull
- Visualization: Chart.js, D3.js
- Reporting: Handlebars, puppeteer (PDF)
```

### Project Structure
```
hubspot-form-analytics/
├── src/
│   ├── api/
│   │   ├── client.js/py          # HubSpot API client
│   │   ├── forms.js/py           # Forms endpoint handlers
│   │   ├── submissions.js/py     # Submissions endpoint handlers
│   │   └── analytics.js/py       # Analytics endpoint handlers
│   ├── data/
│   │   ├── storage.js/py         # Database/file storage layer
│   │   ├── models.js/py          # Data models
│   │   └── migrations/           # Database migrations
│   ├── processing/
│   │   ├── aggregator.js/py      # Metrics aggregation
│   │   ├── transformer.js/py     # Data transformation
│   │   └── analyzer.js/py        # Field & page analysis
│   ├── reporting/
│   │   ├── generator.js/py       # Report generation
│   │   ├── templates/            # Report templates
│   │   └── visualizations.js/py  # Chart generation
│   ├── scheduler/
│   │   ├── jobs.js/py            # Scheduled job definitions
│   │   └── notifications.js/py   # Alert system
│   └── utils/
│       ├── logger.js/py          # Logging utility
│       ├── validators.js/py      # Data validation
│       └── helpers.js/py         # General helpers
├── tests/
│   ├── api/
│   ├── processing/
│   └── reporting/
├── config/
│   ├── config.js/py              # Configuration management
│   └── .env.example              # Environment variables template
├── docs/
│   ├── API.md                    # API documentation
│   └── SETUP.md                  # Setup instructions
├── outputs/                      # Generated reports
├── logs/                         # Application logs
├── package.json / requirements.txt
└── README.md
```

---

## Key Features to Implement

### 1. Form Performance Dashboard
**What it shows**:
- All forms ranked by conversion rate
- Total submissions per form
- Trend indicators (up/down vs previous period)
- Active vs inactive forms
- Forms with declining performance

### 2. Page-Level Analysis
**What it shows**:
- Which pages have forms
- Submission count by page
- Conversion rate by page
- Top performing landing pages
- Pages with forms that have zero submissions

### 3. Field Optimization Report
**What it shows**:
- Field completion rates
- Optional fields that are rarely filled
- Required fields causing drop-off
- Validation error frequency
- Recommendations for field removal/modification

### 4. Time-Series Analysis
**What it shows**:
- Daily/weekly/monthly submission trends
- Seasonal patterns
- Day-of-week performance
- Hour-of-day submission patterns
- Anomaly detection (unusual spikes/drops)

### 5. Conversion Funnel Analysis
**What it shows**:
- Form view → submission conversion
- Multi-step form progression
- Drop-off points in form flow
- Field-by-field completion funnel

### 6. Traffic Source Attribution
**What it shows**:
- Submissions by referrer
- UTM campaign performance
- Direct vs referred submissions
- Channel effectiveness

---

## API Implementation Details

### Example: Fetching All Forms

**Endpoint**: `GET https://api.hubapi.com/marketing/v3/forms`

**Request**:
```bash
curl --request GET \
  --url 'https://api.hubapi.com/marketing/v3/forms?limit=50' \
  --header 'authorization: Bearer YOUR_ACCESS_TOKEN'
```

**Response** (simplified):
```json
{
  "results": [
    {
      "id": "form-guid-1",
      "name": "Newsletter Signup",
      "formType": "HUBSPOT",
      "createdAt": "2024-01-01T00:00:00Z"
    }
  ],
  "paging": {
    "next": {
      "after": "cursor-token-here",
      "link": "?after=cursor-token-here"
    }
  }
}
```

**Pagination Handling**:
```python
def fetch_all_forms(api_token):
    all_forms = []
    url = "https://api.hubapi.com/marketing/v3/forms"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    while url:
        response = requests.get(url, headers=headers)
        data = response.json()
        all_forms.extend(data.get('results', []))
        
        # Check for next page
        next_page = data.get('paging', {}).get('next', {})
        url = f"https://api.hubapi.com/marketing/v3/forms?after={next_page.get('after')}" if next_page else None
    
    return all_forms
```

### Example: Fetching Form Submissions

**Endpoint**: `GET https://api.hubapi.com/form-integrations/v1/submissions/forms/{formGuid}`

**Request**:
```bash
curl --request GET \
  --url 'https://api.hubapi.com/form-integrations/v1/submissions/forms/FORM-GUID?limit=50&after=1704067200000' \
  --header 'authorization: Bearer YOUR_ACCESS_TOKEN'
```

**Query Parameters**:
- `limit`: Number of results (max 50)
- `after`: Timestamp (milliseconds) to fetch submissions after
- `before`: Timestamp (milliseconds) to fetch submissions before

**Response**:
```json
{
  "results": [
    {
      "submittedAt": 1704452400000,
      "values": [
        {"name": "email", "value": "user@example.com"},
        {"name": "firstname", "value": "John"}
      ],
      "pageUrl": "https://example.com/contact",
      "pageTitle": "Contact Us"
    }
  ],
  "paging": {
    "next": {
      "after": "1704538800000"
    }
  }
}
```

### Example: Analytics Data

**Note**: HubSpot's Analytics API v2 is being deprecated. Form analytics should be calculated from submission data.

**Approach**: Calculate metrics from submissions
```python
def calculate_form_metrics(form_id, submissions, start_date, end_date):
    # Filter submissions by date range
    filtered = [s for s in submissions 
                if start_date <= s['submittedAt'] <= end_date]
    
    total_submissions = len(filtered)
    unique_submissions = len(set(s['values'].get('email') for s in filtered))
    
    # Page breakdown
    page_stats = {}
    for submission in filtered:
        page = submission.get('pageUrl')
        if page not in page_stats:
            page_stats[page] = 0
        page_stats[page] += 1
    
    return {
        'form_id': form_id,
        'total_submissions': total_submissions,
        'unique_submissions': unique_submissions,
        'pages': page_stats
    }
```

---

## Data Quality Considerations

### 1. Duplicate Submissions
**Issue**: Users may submit forms multiple times
**Solution**: 
- Track by email + timestamp proximity
- Flag duplicates (within 5 minutes = likely duplicate)
- Provide filtered "unique submissions" metric

### 2. Bot/Spam Submissions
**Issue**: Automated form submissions skew data
**Solution**:
- Check for HubSpot's bot detection flags
- Pattern detection (same IP, rapid submissions)
- Exclude common spam email patterns
- Validate email domains

### 3. Test Submissions
**Issue**: Internal team testing pollutes data
**Solution**:
- Filter known test email addresses
- Exclude company domain emails (optional)
- Flag IP addresses from office

### 4. Incomplete Data
**Issue**: Some submissions may have missing fields
**Solution**:
- Track field completion separately
- Don't exclude incomplete submissions
- Flag forms with high incomplete rates

---

## Performance Optimization

### 1. Caching Strategy
- Cache form configurations (update once per day)
- Cache submission data (only fetch new since last sync)
- Use Redis or in-memory cache for frequently accessed metrics

### 2. Database Indexing
```sql
CREATE INDEX idx_submissions_form_id ON submissions(form_id);
CREATE INDEX idx_submissions_date ON submissions(submitted_at);
CREATE INDEX idx_submissions_page ON submissions(page_url);
CREATE INDEX idx_submissions_email ON submissions(email);
```

### 3. Batch Processing
- Fetch submissions in batches of 50 (API max)
- Process analytics in chunks (e.g., 1000 records at a time)
- Use database transactions for bulk inserts

### 4. Incremental Updates
- Track last sync timestamp
- Only fetch new data since last sync
- Update aggregates incrementally rather than full recalculation

---

## Testing Strategy

### Unit Tests
- API client authentication
- Data transformation functions
- Metrics calculation accuracy
- Date range filtering

### Integration Tests
- End-to-end data fetch and store
- Report generation from sample data
- Scheduling system execution

### Data Validation Tests
- Schema validation for API responses
- Field type validation
- Required field checks
- Data consistency checks

---

## Security Considerations

### 1. API Token Security
- Store in environment variables (never commit to git)
- Use secrets manager in production (AWS Secrets Manager, Azure Key Vault)
- Rotate tokens periodically
- Implement token expiration handling

### 2. Data Privacy
- Handle PII (emails, names, phone numbers) securely
- Consider GDPR/CCPA compliance
- Implement data retention policies
- Option to anonymize contact data in reports

### 3. Access Control
- Restrict access to raw submission data
- Role-based access for reports
- Audit logging for data access

---

## Success Metrics

### Technical Success
- Successfully fetch 100% of form data without errors
- Process and aggregate data in <5 minutes for typical dataset
- Zero data loss during sync operations
- 99.9% uptime for scheduled jobs

### Business Success
- Identify top 3 underperforming forms for optimization
- Reduce form field count by identifying unused optional fields
- Improve average form conversion rate by 15% through insights
- Provide actionable recommendations weekly

---

## Deliverables Checklist

### Core Components
- [ ] HubSpot API client with authentication
- [ ] Form data fetcher (all forms + details)
- [ ] Submission data fetcher with date range filtering
- [ ] Data storage layer (database or file-based)
- [ ] Metrics aggregation engine
- [ ] Page-level analytics processor
- [ ] Field-level analytics processor
- [ ] Time-series data generator

### Reporting
- [ ] Form performance summary report
- [ ] Page performance report
- [ ] Field optimization report
- [ ] Time-series trend report
- [ ] Conversion funnel analysis
- [ ] CSV export functionality
- [ ] HTML dashboard (optional)
- [ ] PDF report generation (optional)

### Automation
- [ ] Daily sync scheduler
- [ ] Weekly report automation
- [ ] Email notification system
- [ ] Alert system for anomalies

### Documentation
- [ ] Setup and installation guide
- [ ] API documentation
- [ ] Report interpretation guide
- [ ] Troubleshooting guide
- [ ] Configuration reference

---

## Timeline Estimate

**Week 1**: Foundation & Data Collection
- Days 1-2: Project setup, authentication, API client
- Days 3-4: Data fetchers and pagination
- Days 5-7: Database/storage layer, error handling

**Week 2**: Data Processing & Analytics
- Days 8-10: Aggregation functions and metrics
- Days 11-12: Field and page analytics
- Days 13-14: Comparison logic and benchmarks

**Week 3**: Reporting & Visualization
- Days 15-16: Report templates and structure
- Days 17-18: Visualization components
- Days 19-21: Filtering and export functionality

**Week 4**: Automation & Polish
- Days 22-23: Scheduling and automation
- Days 24-25: Notifications and alerts
- Days 26-28: Testing, documentation, deployment

**Total**: 4 weeks / 20 working days

---

## Risk Mitigation

### Risk: API Rate Limiting
**Impact**: Data collection failures
**Mitigation**: Implement exponential backoff, request queuing, respect rate limits

### Risk: API Changes
**Impact**: Integration breaks
**Mitigation**: Version-specific endpoints, monitor HubSpot changelog, implement graceful degradation

### Risk: Large Data Volumes
**Impact**: Slow processing, memory issues
**Mitigation**: Pagination, streaming, batch processing, database indexing

### Risk: Missing Historical Data
**Impact**: Incomplete analytics
**Mitigation**: HubSpot may not retain all historical submissions; document limitations

---

## Future Enhancements

### Phase 2 Features
- Form A/B test comparison
- Predictive analytics (forecast submissions)
- Integration with Google Analytics for complete funnel
- Multi-portal support (multiple HubSpot accounts)
- Real-time dashboard (WebSocket updates)
- Mobile app for reports
- Custom metric builder

### Advanced Analytics
- Cohort analysis (submission date-based cohorts)
- Multi-touch attribution
- Form abandonment tracking (requires JavaScript tracking)
- Session replay integration
- Heatmap overlay on forms

---

## Support & Maintenance

### Ongoing Tasks
- Weekly: Review error logs, check sync status
- Monthly: Review API usage, optimize queries
- Quarterly: Update dependencies, security patches
- Annually: Review and update report templates

### Monitoring
- API request success rate
- Data sync completion time
- Database size and growth rate
- Report generation performance
- Error frequency and types

---

## Getting Started Checklist

### Pre-Implementation
- [ ] Obtain HubSpot access token
- [ ] Identify all forms to track
- [ ] Define reporting requirements
- [ ] Choose tech stack
- [ ] Set up development environment

### Implementation
- [ ] Clone/create project repository
- [ ] Install dependencies
- [ ] Configure environment variables
- [ ] Test API connectivity
- [ ] Run first data sync
- [ ] Generate first report

### Deployment
- [ ] Set up production environment
- [ ] Configure scheduled jobs
- [ ] Set up monitoring and alerts
- [ ] Document configuration
- [ ] Train users on reports

---

## Questions to Clarify Before Starting

1. **Data Retention**: How far back should historical data go?
2. **Reporting Frequency**: Daily, weekly, monthly, or on-demand?
3. **Delivery Method**: Email reports, web dashboard, or both?
4. **Access**: Who needs access to which reports?
5. **Alerts**: What metrics should trigger notifications?
6. **Export Format**: CSV, PDF, JSON, or all?
7. **Integration**: Should this feed into other systems (BI tools, CRM)?
8. **Hosting**: Local, cloud, or serverless?

---

## Resources

### HubSpot API Documentation
- Forms API: https://developers.hubspot.com/docs/api/marketing/forms
- Form Submissions: https://developers.hubspot.com/docs/api/marketing/forms/submissions
- CRM Objects: https://developers.hubspot.com/docs/api/crm/objects
- Authentication: https://developers.hubspot.com/docs/api/authentication

### Tools & Libraries
- Python: `hubspot-api-client` (official SDK)
- Node.js: `@hubspot/api-client` (official SDK)
- API Testing: Postman, Insomnia
- Database: PostgreSQL, SQLite
- Visualization: Chart.js, Plotly, D3.js

---

## Conclusion

This integration is highly feasible with HubSpot's robust API. The primary challenge will be handling large volumes of submission data efficiently and creating actionable insights from raw metrics. With proper architecture and incremental development, you'll have a comprehensive form analytics system that provides deep visibility into form performance, identifies optimization opportunities, and drives conversion improvements.

**Recommended First Steps**:
1. Set up API authentication and test basic connectivity
2. Fetch all forms and their configurations
3. Pull submissions for one form as a proof of concept
4. Build basic aggregation (total submissions, conversion rate)
5. Generate a simple CSV report
6. Iterate and expand from there

---

*Document Version: 1.0*  
*Last Updated: February 2, 2026*  
*Created for: Acquisition.com Client Start - HubSpot Form Analytics Integration*
