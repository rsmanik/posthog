# PostHog Headless API Guide

Complete guide to using PostHog's Headless API for programmatic data access.

## Table of Contents

1. [Overview](#overview)
2. [What is "Headless"?](#what-is-headless)
3. [Existing Headless Capabilities](#existing-headless-capabilities)
4. [New Headless API Endpoints](#new-headless-api-endpoints)
5. [Data Transformation Utilities](#data-transformation-utilities)
6. [Usage Examples](#usage-examples)
7. [Integration Guide](#integration-guide)
8. [API Reference](#api-reference)

---

## Overview

PostHog's Headless API allows you to access and manipulate PostHog data programmatically without requiring a browser or UI. It's designed for:

- **CLI Tools & Scripts**: Automate data exports and analysis
- **Mobile Apps**: Build native iOS/Android apps with PostHog data
- **Server-Side Integrations**: Process data in your backend
- **Custom Dashboards**: Create alternative visualizations
- **Scheduled Reports**: Generate and send reports automatically
- **Webhook Integrations**: Send data to external services

**Key Benefits:**
- 🚀 Pure JSON responses (no HTML/CSS/JS)
- 📊 Built-in data transformations
- 💾 Multiple export formats (JSON, CSV)
- 🔄 Optimized for batch operations
- 📡 Webhook-friendly payloads
- ⚡ High-performance query execution

---

## What is "Headless"?

"Headless" means accessing PostHog's data and functionality without a graphical user interface (GUI). Instead of clicking through the PostHog web app, you make HTTP requests directly to API endpoints.

**Traditional (With UI):**
```
User → Browser → PostHog Web App → Visualizations
```

**Headless (Without UI):**
```
Script/App → HTTP Request → PostHog API → Raw Data
```

---

## Existing Headless Capabilities

PostHog **already has powerful headless capabilities** through these endpoints:

### 1. Query API (`/api/query/`)

The Query API is the foundation of PostHog's headless access. It supports all query types:

**Query Types:**
- `TrendsQuery` - Trend analysis over time
- `FunnelsQuery` - Conversion funnel analysis
- `RetentionQuery` - User retention cohorts
- `PathsQuery` - User journey paths
- `StickinessQuery` - Feature stickiness
- `LifecycleQuery` - User lifecycle stages
- `HogQLQuery` - Direct HogQL queries
- `EventsQuery` - Raw event data
- `PersonsQuery` - Person/user data
- `SessionRecordingsQuery` - Session replay metadata

**Example: Execute a Trends Query**
```bash
curl -X POST https://app.posthog.com/api/projects/{project_id}/query/ \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "kind": "TrendsQuery",
      "series": [
        {
          "kind": "EventsNode",
          "event": "$pageview"
        }
      ],
      "dateRange": {
        "date_from": "-30d"
      },
      "interval": "day"
    }
  }'
```

**Response:**
```json
{
  "kind": "TrendsQueryResponse",
  "results": [
    {
      "label": "$pageview",
      "count": 12543,
      "data": [423, 456, 489, ...],
      "days": ["2024-01-01", "2024-01-02", "2024-01-03", ...],
      "labels": ["Jan 1", "Jan 2", "Jan 3", ...]
    }
  ],
  "hasMore": false,
  "dateRange": {
    "date_from": "2023-12-02",
    "date_to": "2024-01-01"
  }
}
```

### 2. Feature Flags API (`/decide`)

Evaluate feature flags programmatically:

```bash
curl -X POST https://app.posthog.com/decide/ \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "YOUR_PROJECT_KEY",
    "distinct_id": "user_123",
    "groups": {
      "company": "acme_corp"
    }
  }'
```

### 3. Event Ingestion (`/capture`, `/batch`)

Send events from any platform:

```bash
curl -X POST https://app.posthog.com/capture/ \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "YOUR_PROJECT_KEY",
    "event": "button_clicked",
    "properties": {
      "button_id": "signup_cta"
    },
    "distinct_id": "user_123"
  }'
```

### 4. Batch Exports

Export data to external destinations (S3, BigQuery, etc.):

```bash
# List batch exports
GET /api/projects/{project_id}/batch_exports/

# Create batch export
POST /api/projects/{project_id}/batch_exports/
```

---

## New Headless API Endpoints

We've added new endpoints specifically optimized for headless use cases:

### Base URL

```
/api/projects/{project_id}/headless/
```

### Available Endpoints

#### 1. Execute Query (Normalized)

Execute any query and get normalized results:

```bash
POST /api/projects/{project_id}/headless/query/execute/
```

**Features:**
- Consistent response structure across query types
- Includes metadata (timings, pagination, etc.)
- Optimized for programmatic parsing

**Example:**
```python
import requests

response = requests.post(
    "https://app.posthog.com/api/projects/123/headless/query/execute/",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "query": {
            "kind": "TrendsQuery",
            "series": [{"kind": "EventsNode", "event": "$pageview"}],
            "dateRange": {"date_from": "-7d"}
        }
    }
)

data = response.json()
print(f"Query type: {data['query_type']}")
print(f"Results count: {len(data['results'])}")
print(f"Metadata: {data['metadata']}")
```

#### 2. Execute Trends (Simplified)

Get simplified trends data:

```bash
POST /api/projects/{project_id}/headless/query/execute/trends/
```

**Features:**
- Simplified response structure
- Removes unnecessary fields
- Optimized for charts and visualizations

#### 3. Execute to CSV

Get results as CSV for exports:

```bash
POST /api/projects/{project_id}/headless/query/execute/csv/
```

**Features:**
- Returns CSV-formatted string
- Proper escaping and quoting
- Ready for import into Excel, Google Sheets, etc.

**Example:**
```bash
curl -X POST https://app.posthog.com/api/projects/123/headless/query/execute/csv/ \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "kind": "EventsQuery",
      "select": ["event", "timestamp", "distinct_id"],
      "limit": 1000
    }
  }' > events.csv
```

#### 4. Execute for Webhook

Get webhook-optimized payload:

```bash
POST /api/projects/{project_id}/headless/query/execute/webhook/
```

**Features:**
- Compact payload
- Includes summary statistics
- Timestamp included
- Minimal overhead

**Example:**
```python
# Send query results to webhook
webhook_data = requests.post(
    "https://app.posthog.com/api/projects/123/headless/query/execute/webhook/",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={"query": {...}}
).json()

# Forward to external service
requests.post("https://your-webhook.com/posthog", json=webhook_data)
```

#### 5. Transform Data

Apply transformations to existing results:

```bash
POST /api/projects/{project_id}/headless/query/transform/
```

**Available Transformations:**
- `flatten` - Flatten breakdown results
- `pivot` - Pivot data for analysis
- `summary` - Calculate summary statistics
- `aggregate` - Aggregate by time period
- `percent_change` - Calculate period-over-period changes
- `csv` - Convert to CSV format

**Example:**
```python
# Transform results without re-executing query
transformed = requests.post(
    "https://app.posthog.com/api/projects/123/headless/query/transform/",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "results": [...],  # Your existing results
        "transform": "summary",
        "options": {"value_field": "count"}
    }
).json()

print(f"Mean: {transformed['result']['mean']}")
print(f"Median: {transformed['result']['median']}")
print(f"Std Dev: {transformed['result']['std_dev']}")
```

---

## Data Transformation Utilities

The `DataTransforms` class provides pure transformation functions:

### Available Transformations

#### 1. Flatten Breakdown Results

Convert nested breakdown data to flat format:

```python
from posthog.api.headless.transforms import DataTransforms

flattened = DataTransforms.flatten_breakdown_results([
    {
        "label": "$pageview",
        "breakdown_value": "Chrome",
        "data": [10, 20, 30],
        "days": ["2024-01-01", "2024-01-02", "2024-01-03"]
    }
])

# Result:
# [
#     {"date": "2024-01-01", "label": "$pageview", "breakdown": "Chrome", "value": 10},
#     {"date": "2024-01-02", "label": "$pageview", "breakdown": "Chrome", "value": 20},
#     ...
# ]
```

#### 2. Pivot Data

Convert from long to wide format:

```python
pivoted = DataTransforms.pivot_breakdown_data(
    results=[
        {"date": "2024-01-01", "breakdown": "Chrome", "value": 10},
        {"date": "2024-01-01", "breakdown": "Firefox", "value": 5}
    ],
    row_field="date",
    column_field="breakdown",
    value_field="value"
)

# Result:
# {
#     "2024-01-01": {"Chrome": 10, "Firefox": 5}
# }
```

#### 3. Summary Statistics

Calculate statistics for a dataset:

```python
stats = DataTransforms.extract_summary_statistics(
    results=[
        {"value": 10},
        {"value": 20},
        {"value": 15}
    ],
    value_field="value"
)

# Result:
# {
#     "count": 3,
#     "sum": 45,
#     "mean": 15.0,
#     "min": 10,
#     "max": 20,
#     "median": 15.0,
#     "std_dev": 4.08
# }
```

#### 4. Percent Change

Calculate period-over-period changes:

```python
changes = DataTransforms.calculate_percent_change(
    current=[{"value": 120}],
    previous=[{"value": 100}],
    value_field="value"
)

# Result:
# [
#     {
#         "value": 120,
#         "previous_value": 100,
#         "percent_change": 20.0
#     }
# ]
```

#### 5. Aggregate by Time Period

Aggregate data over time:

```python
aggregated = DataTransforms.aggregate_by_time_period(
    results=[
        {"date": "2024-01-01", "value": 10},
        {"date": "2024-01-01", "value": 15},
        {"date": "2024-01-02", "value": 20}
    ],
    time_field="date",
    value_field="value",
    aggregation="sum"
)

# Result:
# {
#     "2024-01-01": 25,
#     "2024-01-02": 20
# }
```

#### 6. Convert to CSV

Export to CSV format:

```python
csv_data = DataTransforms.convert_to_csv_format(
    results=[
        {"name": "Alice", "count": 10},
        {"name": "Bob", "count": 20}
    ],
    columns=["name", "count"]
)

# Result:
# "name","count"
# "Alice",10
# "Bob",20
```

---

## Usage Examples

### Example 1: Daily Report Script

Generate and email a daily summary:

```python
#!/usr/bin/env python3
"""
Daily PostHog Report

Generates a daily summary of key metrics and emails it.
"""

import requests
from datetime import datetime, timedelta

POSTHOG_API_KEY = "YOUR_API_KEY"
PROJECT_ID = "123"

def fetch_daily_metrics():
    """Fetch yesterday's metrics"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    response = requests.post(
        f"https://app.posthog.com/api/projects/{PROJECT_ID}/headless/query/execute/",
        headers={"Authorization": f"Bearer {POSTHOG_API_KEY}"},
        json={
            "query": {
                "kind": "TrendsQuery",
                "series": [
                    {"kind": "EventsNode", "event": "$pageview"},
                    {"kind": "EventsNode", "event": "signup"},
                    {"kind": "EventsNode", "event": "purchase"}
                ],
                "dateRange": {
                    "date_from": yesterday,
                    "date_to": yesterday
                }
            }
        }
    ).json()

    return response

def format_report(data):
    """Format metrics into email-friendly text"""
    report = f"📊 PostHog Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"

    for result in data['results']:
        event = result['label']
        count = result['count']
        report += f"{event}: {count:,}\n"

    return report

def send_email(report):
    """Send email with report"""
    # Use your preferred email service
    print(report)  # For now, just print

if __name__ == "__main__":
    metrics = fetch_daily_metrics()
    report = format_report(metrics)
    send_email(report)
```

### Example 2: Custom Dashboard

Build a custom dashboard with any framework:

```javascript
// React Example
import { useState, useEffect } from 'react';

function CustomDashboard() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    async function fetchMetrics() {
      const response = await fetch(
        'https://app.posthog.com/api/projects/123/headless/query/execute/',
        {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer YOUR_API_KEY',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            query: {
              kind: 'TrendsQuery',
              series: [{ kind: 'EventsNode', event: '$pageview' }],
              dateRange: { date_from: '-7d' }
            }
          })
        }
      );

      const data = await response.json();
      setMetrics(data);
    }

    fetchMetrics();
  }, []);

  if (!metrics) return <div>Loading...</div>;

  return (
    <div>
      <h1>Custom Dashboard</h1>
      {metrics.results.map((result, i) => (
        <div key={i}>
          <h2>{result.label}</h2>
          <p>Total: {result.count}</p>
        </div>
      ))}
    </div>
  );
}
```

### Example 3: Slack Bot

Send PostHog data to Slack:

```python
#!/usr/bin/env python3
"""
PostHog Slack Bot

Posts daily metrics to a Slack channel.
"""

import requests
from datetime import datetime

def fetch_metrics():
    """Fetch today's metrics"""
    response = requests.post(
        "https://app.posthog.com/api/projects/123/headless/query/execute/webhook/",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        json={
            "query": {
                "kind": "TrendsQuery",
                "series": [{"kind": "EventsNode", "event": "$pageview"}],
                "dateRange": {"date_from": "-1d"}
            }
        }
    ).json()

    return response

def post_to_slack(data):
    """Post metrics to Slack"""
    slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

    message = {
        "text": f"📊 PostHog Update - {data['timestamp']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Results Count:* {data['results_count']}\n*Mean:* {data['summary']['mean']}"
                }
            }
        ]
    }

    requests.post(slack_webhook, json=message)

if __name__ == "__main__":
    metrics = fetch_metrics()
    post_to_slack(metrics)
```

### Example 4: Mobile App Integration

Use in iOS/Android apps:

```swift
// Swift (iOS) Example
import Foundation

class PostHogClient {
    let apiKey = "YOUR_API_KEY"
    let projectId = "123"
    let baseURL = "https://app.posthog.com"

    func fetchTrends(completion: @escaping (Result<[String: Any], Error>) -> Void) {
        let url = URL(string: "\(baseURL)/api/projects/\(projectId)/headless/query/execute/")!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "query": [
                "kind": "TrendsQuery",
                "series": [
                    ["kind": "EventsNode", "event": "$pageview"]
                ],
                "dateRange": ["date_from": "-7d"]
            ]
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: -1)))
                return
            }

            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                completion(.success(json))
            }
        }.resume()
    }
}
```

### Example 5: Data Export Pipeline

Automated data export to data warehouse:

```python
#!/usr/bin/env python3
"""
PostHog to BigQuery Export

Exports PostHog data to BigQuery on a schedule.
"""

import requests
import pandas as pd
from google.cloud import bigquery

def fetch_events():
    """Fetch events from PostHog"""
    response = requests.post(
        "https://app.posthog.com/api/projects/123/headless/query/execute/",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        json={
            "query": {
                "kind": "EventsQuery",
                "select": ["event", "timestamp", "distinct_id", "properties"],
                "limit": 10000
            }
        }
    ).json()

    return response['results']

def export_to_bigquery(events):
    """Export events to BigQuery"""
    client = bigquery.Client()
    table_id = "your-project.your-dataset.posthog_events"

    df = pd.DataFrame(events)

    job = client.load_table_from_dataframe(df, table_id)
    job.result()

    print(f"Loaded {len(df)} rows into {table_id}")

if __name__ == "__main__":
    events = fetch_events()
    export_to_bigquery(events)
```

---

## Integration Guide

### Step 1: Get Your API Key

1. Go to PostHog Settings → Personal API Keys
2. Create a new API key with appropriate scopes
3. Keep it secure!

### Step 2: Choose Your Integration Method

**Option A: Direct HTTP Requests**
- Use `curl`, `requests`, `fetch()`, etc.
- Full control, works in any language

**Option B: Use PostHog SDKs**
- Use existing SDKs for your language
- Easier setup, built-in retry logic

**Option C: Use Auto-Generated Client (TypeScript)**
- Use the new OpenAPI-generated client (from Phase 1.1)
- Full type safety
- See `frontend/docs/API_CLIENT.md`

### Step 3: Make Your First Request

```bash
# Test with curl
curl -X POST https://app.posthog.com/api/projects/YOUR_PROJECT_ID/query/ \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "kind": "TrendsQuery",
      "series": [{"kind": "EventsNode", "event": "$pageview"}],
      "dateRange": {"date_from": "-7d"}
    }
  }'
```

### Step 4: Handle Responses

**Success Response (200):**
```json
{
  "kind": "TrendsQueryResponse",
  "results": [...],
  "hasMore": false
}
```

**Error Response (4xx/5xx):**
```json
{
  "detail": "Error message",
  "code": "error_code"
}
```

### Step 5: Implement Error Handling

```python
import requests
from time import sleep

def fetch_with_retry(url, data, max_retries=3):
    """Fetch with exponential backoff"""
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                # Server error, retry
                sleep(2 ** attempt)
                continue
            else:
                # Client error, don't retry
                raise
        except requests.exceptions.RequestException as e:
            # Network error, retry
            sleep(2 ** attempt)
            continue

    raise Exception(f"Failed after {max_retries} retries")
```

---

## API Reference

### Authentication

All requests require authentication via Personal API Key:

```
Authorization: Bearer YOUR_API_KEY
```

### Rate Limiting

- **Sustained**: 240 requests per minute
- **Burst**: 480 requests per minute

Rate limit headers:
- `X-RateLimit-Limit`: Total limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

### Query Types

Full schema documentation available at `/api/schema/`

**Common Query Types:**
- `TrendsQuery` - Time series analysis
- `FunnelsQuery` - Conversion funnels
- `RetentionQuery` - Cohort retention
- `PathsQuery` - User paths
- `HogQLQuery` - Raw SQL-like queries
- `EventsQuery` - Event listings
- `PersonsQuery` - Person data

### Response Formats

**Standard Response:**
```json
{
  "kind": "QueryResponseType",
  "results": [...],
  "hasMore": boolean,
  "limit": number,
  "offset": number
}
```

**CSV Response:**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="export.csv"

"column1","column2"
"value1","value2"
```

### Error Codes

- `400` - Bad Request (invalid query)
- `401` - Unauthorized (invalid API key)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (invalid project/resource)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error
- `503` - Service Unavailable

---

## Next Steps

1. **Phase 1.3**: [Headless Dashboard Renderer](./HEADLESS_ARCHITECTURE_PHASE1.3_SUMMARY.md)
2. **Phase 2**: [Frontend Data Layer Refactoring](./HEADLESS_ARCHITECTURE_PHASE2_SUMMARY.md)
3. **Phase 3**: [Performance Optimizations](./HEADLESS_ARCHITECTURE_PHASE3_SUMMARY.md)

---

## Resources

- [PostHog API Documentation](https://posthog.com/docs/api)
- [HogQL Reference](https://posthog.com/docs/hogql)
- [Query Schema](https://posthog.com/docs/api/query)
- [OpenAPI Spec](https://app.posthog.com/api/schema/)
- [Auto-Generated Client Guide](./frontend/docs/API_CLIENT.md)

---

## Support

Need help?

- 📖 [Documentation](https://posthog.com/docs)
- 💬 [Community Slack](https://posthog.com/slack)
- 🐛 [GitHub Issues](https://github.com/posthog/posthog/issues)
- 📧 [Support Email](mailto:hey@posthog.com)
