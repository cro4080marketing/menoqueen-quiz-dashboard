# Shopify Product Page Analytics - Context Document

## Project Overview
Build a Shopify analytics application that tracks and compares product page performance across multiple URLs with customizable date ranges and order tag filtering. The interface should be clean and data-focused, inspired by Triple Whale's design approach.

## Core Functionality

### 1. Metrics to Track
For each product page URL, calculate and display:
- **Sessions**: Total page view sessions
- **Total Revenue**: Sum of all attributed order revenue
- **Revenue per Visitor**: Total Revenue / Sessions
- **Conversion Rate**: (Orders / Sessions) × 100
- **Average Order Value (AOV)**: Total Revenue / Number of Orders

### 2. Data Sources & Attribution

#### Shopify Analytics API
- Use for session/traffic data at the page URL level
- Track individual product page sessions

#### Shopify Orders API
- Pull order data including:
  - Order value (total_price)
  - Order tags
  - Timestamp (created_at)
  - Attribution data (landing_site, referring_site, source_url)

#### Attribution Logic (Priority Order)
1. **Primary**: Landing page URL from the session that converted
2. **Secondary**: Last page visited before checkout
3. **Optional**: Also support referrer data and UTM parameters as alternative attribution methods
4. Make attribution method selectable in the UI

### 3. Order Tag Filtering
- Allow filtering by ANY order tag that exists in Shopify
- Filter should be dynamic - user enters tag name(s) to filter by
- Common use case: "subscription first order" tag to identify subscription vs one-time purchases
- Support multiple tag filters with AND/OR logic
- Show tag suggestions based on existing order tags in the store

### 4. Comparison View (Critical Feature)

#### Multi-Page Side-by-Side Comparison
- Display multiple product page URLs in side-by-side columns
- Example layout:
  ```
  Date Range: [Jan 1 - Jan 31, 2024]  [Apply to All]
  
  | Metric              | Page A          | Page B          | Page C          |
  |---------------------|-----------------|-----------------|-----------------|
  | Sessions            | 1,234           | 2,456           | 890             |
  | Total Revenue       | $12,450         | $23,100         | $8,900          |
  | Revenue/Visitor     | $10.09          | $9.41           | $10.00          |
  | Conversion Rate     | 3.2%            | 2.8%            | 3.5%            |
  | AOV                 | $98.50          | $105.20         | $95.00          |
  ```

#### Date Range Behavior
- Single date range picker affects ALL columns simultaneously
- When date range changes, all page metrics recalculate for that period
- No period A vs period B comparisons - this is page vs page comparison only
- Support custom date ranges and common presets (Last 7 days, Last 30 days, Last 90 days, etc.)

#### UX Requirements
- Keep the interface clean even with multiple columns (3-5 pages typical)
- Allow adding/removing page URLs dynamically
- Show percentage differences between pages for quick comparison
- Highlight best/worst performers per metric
- Make it visually clear which metrics are "better" when higher vs lower

### 5. Report Export
- Generate PDF reports containing:
  - Selected date range
  - All compared pages and their metrics
  - Applied filters (tags, attribution method)
  - Visual formatting similar to the on-screen view
  - Company/store branding area
  - Timestamp of report generation
- Download button prominently placed
- File naming: `shopify-analytics-[store-name]-[date-range].pdf`

## Technical Requirements

### Authentication & Setup
- **Shopify OAuth 2.0** (required - legacy API tokens no longer supported)
- Implement standard Shopify embedded app authentication flow
- Required API scopes:
  - `read_analytics` - for session/traffic data
  - `read_orders` - for order data and tags
  - `read_products` - for product/page information

### Data Refresh Strategy
- **On-demand refresh** when viewing reports
- No background cron jobs or scheduled updates
- Cache data temporarily during session to avoid excessive API calls
- Show "last updated" timestamp
- Include manual refresh button

### API Integration Details

#### Shopify Analytics API
- Endpoint: `/admin/api/2024-01/analytics/reports.json`
- Query parameters for page-level session data
- Filter by URL path/product handle
- Date range filtering

#### Shopify Orders API
- Endpoint: `/admin/api/2024-01/orders.json`
- Include fields: `total_price`, `tags`, `created_at`, `landing_site`, `referring_site`, `source_url`
- Pagination handling (Shopify limits to 250 orders per request)
- Date range filtering via `created_at_min` and `created_at_max`

### Deployment
- **Platform**: Railway
- Environment variables:
  - `SHOPIFY_API_KEY`
  - `SHOPIFY_API_SECRET`
  - `SHOPIFY_SCOPES`
  - `DATABASE_URL` (for storing OAuth tokens and cached data)
  - `APP_URL` (for OAuth redirect)
- Include `railway.json` or `Procfile` for deployment config
- Database for persisting:
  - OAuth access tokens per store
  - Temporary query caching
  - User preferences

### Recommended Tech Stack
Since there's no specific preference, recommend modern, maintainable stack:

**Frontend:**
- Next.js 14+ (React framework)
- Shopify Polaris (official Shopify design system - ensures familiar UX)
- Tailwind CSS (for custom styling beyond Polaris)
- Recharts or Chart.js (if adding visualizations)

**Backend:**
- Next.js API routes (serverless functions on Railway)
- Node.js runtime

**Database:**
- PostgreSQL (Railway provides managed PostgreSQL)
- Prisma ORM (type-safe database access)

**PDF Generation:**
- jsPDF or Puppeteer (for high-quality PDF rendering)

**Shopify Integration:**
- @shopify/shopify-api (official Node.js library)
- Handles OAuth, API requests, webhooks

## UI/UX Design Principles (Triple Whale Inspired)

### Visual Design
- Clean, minimal interface with focus on data
- Large, readable numbers for key metrics
- Use of cards/panels to separate different sections
- Subtle use of color for status indicators (green for good, red for needs attention)
- Plenty of white space

### Layout Structure
```
┌─────────────────────────────────────────────────────┐
│ Header: Store Name | Date Range Picker | Export PDF │
├─────────────────────────────────────────────────────┤
│ Filters: Tag Filter | Attribution Method             │
├─────────────────────────────────────────────────────┤
│ Page Selector: [Add Page URL] [Page URL 1] [×]      │
│                 [Page URL 2] [×] [Page URL 3] [×]    │
├─────────────────────────────────────────────────────┤
│                 METRICS TABLE                        │
│  Multi-column comparison view                        │
│  Clear headers, aligned numbers                      │
│  Highlight best/worst per row                        │
├─────────────────────────────────────────────────────┤
│ Footer: Last Updated: [timestamp] [Refresh Data]    │
└─────────────────────────────────────────────────────┘
```

### Interaction Patterns
- Drag-and-drop to reorder page columns (optional enhancement)
- Inline editing of page URLs
- Quick-add common pages from dropdown (top products)
- Keyboard shortcuts for power users
- Loading states that don't block the entire UI
- Error messages that are helpful and actionable

## Data Calculation Notes

### Sessions Calculation
- Use Shopify Analytics API for accurate session counts
- Sessions = unique browsing sessions that viewed the specific page URL
- Important: Shopify may attribute sessions differently than GA4

### Revenue Attribution
- Match orders to page URLs via attribution logic
- Handle multi-touch scenarios (user visited multiple pages)
- In multi-touch, you may need to decide on attribution model:
  - First touch (landing page)
  - Last touch (last page before checkout)
  - Consider making this configurable

### Conversion Rate Precision
- Calculate as: (Number of attributed orders / Sessions) × 100
- Display to 2 decimal places
- Handle edge cases (zero sessions = N/A or 0%)

### AOV Calculation
- Simple average: Total Revenue / Number of Orders
- Display in currency format with 2 decimal places
- Consider including median AOV as additional metric (more resistant to outliers)

## Development Phases

### Phase 1: MVP
- [ ] Shopify OAuth authentication
- [ ] Basic page URL input (manual entry)
- [ ] Single date range picker
- [ ] Fetch sessions from Analytics API
- [ ] Fetch orders from Orders API
- [ ] Calculate 5 core metrics
- [ ] Display in simple table format
- [ ] Support 2-3 page comparison

### Phase 2: Filtering & Attribution
- [ ] Order tag filtering (single tag)
- [ ] Attribution method selector
- [ ] Multiple tag filters with AND/OR logic
- [ ] Tag autocomplete/suggestions

### Phase 3: UI Polish
- [ ] Implement Shopify Polaris design
- [ ] Add/remove pages dynamically
- [ ] Highlight best/worst performers
- [ ] Responsive design
- [ ] Loading states and error handling

### Phase 4: Export & Deployment
- [ ] PDF report generation
- [ ] Railway deployment configuration
- [ ] Environment variable setup
- [ ] Database migrations
- [ ] Production testing

### Phase 5: Enhancements (Optional)
- [ ] Save report configurations
- [ ] Share reports via link
- [ ] Email scheduled reports
- [ ] Add charts/visualizations
- [ ] Bulk page import (CSV)
- [ ] API rate limit handling and optimization

## Important Considerations

### Shopify API Limits
- REST Admin API: 2 requests/second (burst up to 40)
- GraphQL Admin API: 50 points/second (consider migrating to GraphQL for better performance)
- Implement rate limiting and retry logic
- Cache aggressively where appropriate

### Data Accuracy
- Shopify Analytics API may have 24-48 hour data delay
- Set expectations in UI about data freshness
- Consider adding "preliminary data" disclaimers for recent dates

### Performance
- Large date ranges can require many API calls (pagination)
- Implement progress indicators for long-running queries
- Consider background job queue for very large reports (optional)

### Security
- Store OAuth tokens securely (encrypted in database)
- Implement CSRF protection
- Validate all user inputs (URLs, tags, date ranges)
- Use environment variables for all secrets
- Implement proper session management

### Edge Cases to Handle
- No orders in selected date range
- Invalid product page URLs
- Tags that don't exist
- Deleted products
- Refunded/cancelled orders (decide how to handle)
- Orders with multiple products (attribution logic)

## Success Metrics for This Tool
- Accurately calculates all 5 metrics
- Handles 5+ page comparisons smoothly
- Generates professional PDF reports
- Loads data in <5 seconds for 30-day ranges
- Zero-friction Shopify OAuth setup
- Intuitive UI that requires no documentation

## File Structure Recommendation
```
shopify-analytics/
├── README.md
├── package.json
├── railway.json
├── prisma/
│   └── schema.prisma
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth/
│   │   │   │   └── callback/route.ts
│   │   │   ├── shopify/
│   │   │   │   ├── analytics/route.ts
│   │   │   │   └── orders/route.ts
│   │   │   └── reports/
│   │   │       ├── generate/route.ts
│   │   │       └── export/route.ts
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   ├── DateRangePicker.tsx
│   │   ├── MetricsTable.tsx
│   │   ├── PageSelector.tsx
│   │   ├── TagFilter.tsx
│   │   └── ExportButton.tsx
│   ├── lib/
│   │   ├── shopify.ts
│   │   ├── analytics.ts
│   │   ├── calculations.ts
│   │   └── pdf-generator.ts
│   └── types/
│       └── index.ts
└── .env.example
```

## Questions to Resolve During Development
1. Should refunded orders be excluded from revenue calculations?
2. How to handle partially refunded orders?
3. Should cancelled orders be included in order count?
4. Display net revenue (after refunds) or gross revenue?
5. Time zone handling - use store's timezone or UTC?
6. Should there be user accounts, or one-to-one app-to-store relationship?
7. Max number of simultaneous page comparisons (recommend 5-6 for UX)?

## Resources & Documentation
- [Shopify Admin API Reference](https://shopify.dev/docs/api/admin)
- [Shopify OAuth Documentation](https://shopify.dev/docs/apps/auth/oauth)
- [Shopify Analytics API](https://shopify.dev/docs/api/admin-rest/latest/resources/analytics)
- [Shopify Polaris Design System](https://polaris.shopify.com/)
- [Railway Deployment Docs](https://docs.railway.app/)
- [Triple Whale](https://www.triplewhale.com/) - for UI/UX inspiration

---

**Next Steps**: Use this context document with Claude Code to begin implementation. Start with Phase 1 (MVP) to establish core functionality, then iterate through subsequent phases.