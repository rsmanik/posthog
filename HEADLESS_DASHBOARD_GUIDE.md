# Headless Dashboard Rendering API Guide

## Overview

The Headless Dashboard Rendering API provides programmatic access to PostHog dashboards in various formats, enabling headless/automated consumption for:

- **Scheduled Reports**: Generate dashboard snapshots for email reports
- **Custom Integrations**: Embed dashboard data in external tools
- **Mobile Applications**: Retrieve dashboard data for native mobile apps
- **Monitoring Systems**: Export dashboard data for alerting and monitoring
- **Data Pipelines**: Extract dashboard data for further processing

## Key Features

- **Multiple Export Formats**: PNG screenshots, JSON structure, raw data
- **Flexible Filtering**: Apply dashboard filters programmatically
- **Efficient Caching**: PNG exports are cached to avoid redundant rendering
- **Async Processing**: PNG generation runs asynchronously via Celery
- **Tile-Level Data**: Access individual tile query results
- **Layout Information**: Optional layout metadata for custom rendering

## API Endpoints

All endpoints require authentication and are nested under team/environment:

```
/api/environments/{team_id}/headless/dashboards/
/api/projects/{team_id}/headless/dashboards/  (legacy)
```

### 1. Generic Render Endpoint

**POST** `/api/environments/{team_id}/headless/dashboards/{dashboard_id}/render/`

Auto-detects format and delegates to appropriate renderer.

**Request Body**:
```json
{
  "format": "json",           // "png", "json", or "json_data"
  "filters": {                // Optional dashboard filters
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  },
  "width": 1920,              // PNG width in pixels
  "height": null,             // PNG height (auto if null)
  "max_age_seconds": 3600,    // Max age for cached PNG
  "include_data": true,       // Include query data (JSON only)
  "include_layout": true      // Include layout info (JSON only)
}
```

**Response** (format-dependent):
```json
// For PNG format
{
  "export_id": 123,
  "status": "processing",  // or "complete"
  "url": "/api/projects/456/exported_assets/123/content",
  "created_at": "2024-01-15T10:30:00Z"
}

// For JSON format
{
  "id": 789,
  "name": "My Dashboard",
  "tiles": [...],
  "tiles_count": 5
}
```

### 2. PNG Export Endpoint

**POST** `/api/environments/{team_id}/headless/dashboards/{dashboard_id}/render/png/`

Generates a PNG screenshot of the dashboard using Selenium.

**Request Body**:
```json
{
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  },
  "width": 1920,
  "height": null,
  "max_age_seconds": 3600
}
```

**Response**:
```json
{
  "export_id": 123,
  "status": "processing",
  "url": null,  // Available when status is "complete"
  "created_at": "2024-01-15T10:30:00Z",
  "dashboard_id": 789
}
```

**Notes**:
- Export is asynchronous and may take 5-30 seconds
- Returns cached export if recent one exists (within `max_age_seconds`)
- Poll `/api/projects/{team_id}/exported_assets/{export_id}/` to check status
- Download content from `url` when status is "complete"

### 3. JSON Export Endpoint

**POST** `/api/environments/{team_id}/headless/dashboards/{dashboard_id}/render/json/`

Returns complete dashboard structure with optional query data.

**Request Body**:
```json
{
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  },
  "include_data": true,
  "include_layout": true
}
```

**Response**:
```json
{
  "id": 789,
  "name": "Weekly Metrics Dashboard",
  "description": "Key metrics for the week",
  "pinned": true,
  "created_at": "2024-01-01T00:00:00Z",
  "created_by": {
    "id": 42,
    "email": "user@example.com"
  },
  "tags": ["weekly", "metrics"],
  "filters": {},
  "tiles": [
    {
      "id": 101,
      "insight_id": 201,
      "layouts": {
        "sm": {"x": 0, "y": 0, "w": 6, "h": 5},
        "xs": {"x": 0, "y": 0, "w": 6, "h": 5}
      },
      "color": "blue",
      "insight": {
        "id": 201,
        "name": "Page Views Trend",
        "description": "Daily page views",
        "favorited": false,
        "filters": {},
        "query": {...},
        "tags": ["pageviews"],
        "data": {
          "kind": "TrendsQuery",
          "results": [...]
        }
      }
    }
  ],
  "tiles_count": 5
}
```

### 4. Data-Only Export Endpoint

**POST** `/api/environments/{team_id}/headless/dashboards/{dashboard_id}/render/data/`

Returns only query results without structure/layout.

**Request Body**:
```json
{
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  }
}
```

**Response**:
```json
{
  "101": {
    "insight_id": 201,
    "insight_name": "Page Views Trend",
    "data": {
      "kind": "TrendsQuery",
      "results": [...]
    }
  },
  "102": {
    "insight_id": 202,
    "insight_name": "User Signups",
    "data": {
      "kind": "TrendsQuery",
      "results": [...]
    }
  }
}
```

### 5. Dashboard Summary Endpoint

**GET** `/api/environments/{team_id}/headless/dashboards/{dashboard_id}/summary/`

Returns lightweight dashboard metadata without executing queries.

**Response**:
```json
{
  "id": 789,
  "name": "Weekly Metrics Dashboard",
  "description": "Key metrics for the week",
  "tiles_count": 5,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "tags": ["weekly", "metrics"],
  "is_shared": false
}
```

## Usage Examples

### Example 1: Daily Email Report with PNG Screenshot

Generate a PNG screenshot and email it to stakeholders.

```python
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import time

POSTHOG_API_URL = "https://app.posthog.com/api"
POSTHOG_API_KEY = "phx_..."
TEAM_ID = 123
DASHBOARD_ID = 789

def generate_daily_report():
    """Generate and email a dashboard screenshot."""

    # Request PNG export
    response = requests.post(
        f"{POSTHOG_API_URL}/environments/{TEAM_ID}/headless/dashboards/{DASHBOARD_ID}/render/png/",
        headers={
            "Authorization": f"Bearer {POSTHOG_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "filters": {
                "date_from": "-7d",
                "date_to": "now"
            },
            "width": 1920,
            "max_age_seconds": 3600,  # Use cached if < 1 hour old
        }
    )

    export_data = response.json()
    export_id = export_data["export_id"]

    # Poll for completion
    max_attempts = 60
    for attempt in range(max_attempts):
        status_response = requests.get(
            f"{POSTHOG_API_URL}/projects/{TEAM_ID}/exported_assets/{export_id}/",
            headers={"Authorization": f"Bearer {POSTHOG_API_KEY}"}
        )

        status_data = status_response.json()

        if status_data["has_content"]:
            # Download PNG
            content_url = f"{POSTHOG_API_URL}/projects/{TEAM_ID}/exported_assets/{export_id}/content"
            image_response = requests.get(
                content_url,
                headers={"Authorization": f"Bearer {POSTHOG_API_KEY}"}
            )

            # Send email
            send_email_with_dashboard(image_response.content)
            return

        time.sleep(2)  # Wait 2 seconds before retry

    raise TimeoutError("Dashboard export did not complete in time")

def send_email_with_dashboard(image_data: bytes):
    """Send email with dashboard screenshot."""
    msg = MIMEMultipart()
    msg["From"] = "reports@company.com"
    msg["To"] = "team@company.com"
    msg["Subject"] = "Daily Dashboard Report"

    # Add text
    text = MIMEText("Please find attached your daily dashboard report.", "plain")
    msg.attach(text)

    # Add image
    image = MIMEImage(image_data, name="dashboard.png")
    msg.attach(image)

    # Send via SMTP
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("reports@company.com", "password")
        server.send_message(msg)

# Run daily via cron
generate_daily_report()
```

### Example 2: Real-Time Dashboard for Mobile App

Fetch dashboard data for a mobile app display.

```swift
// Swift example for iOS app
import Foundation

struct DashboardData: Codable {
    let id: Int
    let name: String
    let tiles: [DashboardTile]
    let tilesCount: Int

    enum CodingKeys: String, CodingKey {
        case id, name, tiles
        case tilesCount = "tiles_count"
    }
}

struct DashboardTile: Codable {
    let id: Int
    let insight: TileInsight?
}

struct TileInsight: Codable {
    let id: Int
    let name: String
    let data: [String: Any]?
}

class DashboardService {
    let baseURL = "https://app.posthog.com/api"
    let apiKey = "phx_..."
    let teamId = 123

    func fetchDashboard(dashboardId: Int, completion: @escaping (Result<DashboardData, Error>) -> Void) {
        let url = URL(string: "\(baseURL)/environments/\(teamId)/headless/dashboards/\(dashboardId)/render/json/")!

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "filters": [
                "date_from": "-30d",
                "date_to": "now"
            ],
            "include_data": true,
            "include_layout": false  // Don't need layout for mobile
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 0)))
                return
            }

            do {
                let dashboard = try JSONDecoder().decode(DashboardData.self, from: data)
                completion(.success(dashboard))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}

// Usage in View Controller
let dashboardService = DashboardService()
dashboardService.fetchDashboard(dashboardId: 789) { result in
    switch result {
    case .success(let dashboard):
        DispatchQueue.main.async {
            self.updateUI(with: dashboard)
        }
    case .failure(let error):
        print("Error: \(error)")
    }
}
```

### Example 3: Slack Bot for Dashboard Monitoring

Monitor dashboard metrics and alert via Slack when thresholds are exceeded.

```python
import requests
import time
from slack_sdk import WebClient

POSTHOG_API_URL = "https://app.posthog.com/api"
POSTHOG_API_KEY = "phx_..."
SLACK_TOKEN = "xoxb-..."
TEAM_ID = 123
DASHBOARD_ID = 789

slack_client = WebClient(token=SLACK_TOKEN)

def check_dashboard_metrics():
    """Check dashboard metrics and alert if thresholds exceeded."""

    # Fetch dashboard data
    response = requests.post(
        f"{POSTHOG_API_URL}/environments/{TEAM_ID}/headless/dashboards/{DASHBOARD_ID}/render/data/",
        headers={
            "Authorization": f"Bearer {POSTHOG_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "filters": {
                "date_from": "-24h",
                "date_to": "now"
            }
        }
    )

    tiles_data = response.json()

    # Check each tile for threshold violations
    alerts = []

    for tile_id, tile_data in tiles_data.items():
        if "error" in tile_data:
            continue

        insight_name = tile_data["insight_name"]
        results = tile_data["data"].get("results", [])

        # Example: Check if total events < threshold
        if insight_name == "Total Events":
            total = sum(series.get("count", 0) for series in results)
            if total < 1000:
                alerts.append(f"⚠️ *{insight_name}*: Only {total} events in last 24h (threshold: 1000)")

        # Example: Check error rate
        if insight_name == "Error Rate":
            for series in results:
                if series.get("breakdown_value") == "error":
                    error_rate = series.get("aggregated_value", 0)
                    if error_rate > 5.0:
                        alerts.append(f"🚨 *{insight_name}*: {error_rate:.2f}% (threshold: 5%)")

    # Send Slack alerts
    if alerts:
        message = "Dashboard Alert 📊\n\n" + "\n".join(alerts)
        slack_client.chat_postMessage(
            channel="#alerts",
            text=message
        )

    return alerts

# Run every 5 minutes
while True:
    try:
        alerts = check_dashboard_metrics()
        if alerts:
            print(f"Sent {len(alerts)} alerts")
        else:
            print("No alerts")
    except Exception as e:
        print(f"Error: {e}")

    time.sleep(300)  # 5 minutes
```

### Example 4: Data Pipeline Export

Export dashboard data to a data warehouse for further analysis.

```python
import requests
import pandas as pd
from sqlalchemy import create_engine

POSTHOG_API_URL = "https://app.posthog.com/api"
POSTHOG_API_KEY = "phx_..."
TEAM_ID = 123
DASHBOARD_ID = 789
DB_URL = "postgresql://user:pass@localhost/warehouse"

def export_dashboard_to_warehouse():
    """Export dashboard data to data warehouse."""

    # Fetch dashboard with all data
    response = requests.post(
        f"{POSTHOG_API_URL}/environments/{TEAM_ID}/headless/dashboards/{DASHBOARD_ID}/render/json/",
        headers={
            "Authorization": f"Bearer {POSTHOG_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "filters": {
                "date_from": "-7d",
                "date_to": "now"
            },
            "include_data": true,
            "include_layout": false
        }
    )

    dashboard = response.json()

    # Create database connection
    engine = create_engine(DB_URL)

    # Export each tile's data
    for tile in dashboard["tiles"]:
        if not tile.get("insight") or "error" in tile["insight"].get("data", {}):
            continue

        insight = tile["insight"]
        insight_name = insight["name"]
        results = insight["data"].get("results", [])

        # Flatten results to DataFrame
        rows = []
        for series in results:
            label = series.get("label", "")
            breakdown = series.get("breakdown_value", "")
            data_points = series.get("data", [])
            days = series.get("days", [])

            for idx, value in enumerate(data_points):
                rows.append({
                    "dashboard_id": DASHBOARD_ID,
                    "dashboard_name": dashboard["name"],
                    "insight_id": insight["id"],
                    "insight_name": insight_name,
                    "label": label,
                    "breakdown": breakdown,
                    "date": days[idx] if idx < len(days) else None,
                    "value": value,
                })

        if rows:
            df = pd.DataFrame(rows)

            # Write to database
            table_name = f"posthog_dashboard_{DASHBOARD_ID}_tile_{tile['id']}"
            df.to_sql(
                table_name,
                engine,
                if_exists="replace",
                index=False
            )

            print(f"Exported {len(rows)} rows to {table_name}")

# Run daily via scheduler
export_dashboard_to_warehouse()
```

### Example 5: Custom Web Dashboard

Build a custom web dashboard using dashboard data.

```javascript
// JavaScript/React example
import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

const POSTHOG_API_URL = 'https://app.posthog.com/api';
const POSTHOG_API_KEY = 'phx_...';
const TEAM_ID = 123;
const DASHBOARD_ID = 789;

function CustomDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await fetch(
        `${POSTHOG_API_URL}/environments/${TEAM_ID}/headless/dashboards/${DASHBOARD_ID}/render/json/`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${POSTHOG_API_KEY}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            filters: {
              date_from: '-30d',
              date_to: 'now'
            },
            include_data: true,
            include_layout: false
          })
        }
      );

      const data = await response.json();
      setDashboardData(data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!dashboardData) return null;

  return (
    <div className="custom-dashboard">
      <h1>{dashboardData.name}</h1>
      <p>{dashboardData.description}</p>

      {dashboardData.tiles.map(tile => {
        if (!tile.insight || !tile.insight.data) return null;

        const insight = tile.insight;
        const results = insight.data.results || [];

        // Convert to chart-friendly format
        const chartData = [];
        if (results.length > 0) {
          const series = results[0];
          const days = series.days || [];
          const values = series.data || [];

          days.forEach((day, idx) => {
            chartData.push({
              date: day,
              value: values[idx] || 0
            });
          });
        }

        return (
          <div key={tile.id} className="dashboard-tile">
            <h2>{insight.name}</h2>
            <LineChart width={600} height={300} data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="value" stroke="#8884d8" />
            </LineChart>
          </div>
        );
      })}
    </div>
  );
}

export default CustomDashboard;
```

## Best Practices

### 1. Use Appropriate Export Format

- **PNG**: For email reports, presentations, human consumption
- **JSON (full)**: For custom rendering with layout preservation
- **JSON (data-only)**: For data analysis, mobile apps, integrations
- **Summary**: For dashboard listings, quick checks

### 2. Leverage Caching

PNG exports are cached automatically. Set `max_age_seconds` appropriately:

```python
# For real-time reports (no caching)
"max_age_seconds": 0

# For hourly reports (cache for 1 hour)
"max_age_seconds": 3600

# For daily reports (cache for 24 hours)
"max_age_seconds": 86400
```

### 3. Handle Async PNG Generation

PNG generation is asynchronous. Always poll for completion:

```python
def wait_for_export(export_id, max_wait=120):
    """Wait for export to complete."""
    start = time.time()

    while time.time() - start < max_wait:
        response = requests.get(
            f"{API_URL}/projects/{TEAM_ID}/exported_assets/{export_id}/",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )

        if response.json()["has_content"]:
            return True

        time.sleep(2)

    return False
```

### 4. Apply Filters for Flexibility

Use dashboard filters to customize data ranges:

```python
# Last 7 days
"filters": {"date_from": "-7d", "date_to": "now"}

# Specific date range
"filters": {"date_from": "2024-01-01", "date_to": "2024-01-31"}

# This month
"filters": {"date_from": "-1mStart", "date_to": "now"}

# Custom properties
"filters": {
    "date_from": "-30d",
    "properties": [
        {"key": "country", "value": ["US", "UK"], "operator": "exact"}
    ]
}
```

### 5. Error Handling

Always handle errors gracefully:

```python
def fetch_dashboard_safe(dashboard_id):
    """Fetch dashboard with error handling."""
    try:
        response = requests.post(
            f"{API_URL}/environments/{TEAM_ID}/headless/dashboards/{dashboard_id}/render/data/",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"filters": {"date_from": "-7d", "date_to": "now"}},
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        # Check for tile-level errors
        for tile_id, tile_data in data.items():
            if "error" in tile_data:
                print(f"Tile {tile_id} error: {tile_data['error']}")

        return data

    except requests.exceptions.Timeout:
        print("Request timed out")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return None
```

## Performance Considerations

### Query Execution

- Dashboard rendering executes all tile queries synchronously
- Large dashboards with many tiles may take 10-30 seconds
- Use `include_data: false` for faster metadata-only fetches
- Consider fetching individual tiles via `/api/query/` for large dashboards

### Caching Strategy

- PNG exports use aggressive caching (check `max_age_seconds`)
- JSON/data exports are not cached (always fresh)
- For high-frequency access, cache results client-side

### Rate Limiting

- Be mindful of API rate limits (varies by plan)
- For bulk exports, implement exponential backoff
- Consider batching requests during off-peak hours

## Troubleshooting

### Issue: PNG Export Stuck in "processing"

**Solution**: PNG generation may fail due to:
- Selenium/browser issues on server
- Dashboard rendering timeout (>60s)
- Missing fonts or assets

Check export logs or contact support.

### Issue: Tile Data Shows "error"

**Solution**: Individual tile queries may fail due to:
- Invalid query syntax
- Missing data/events
- Insufficient permissions

Check the error message in the `error` field.

### Issue: Dashboard Not Found

**Solution**: Verify:
- Dashboard ID is correct
- Team ID matches dashboard's team
- API key has access to the dashboard

### Issue: Slow Response Times

**Solution**:
- Use `include_data: false` to skip query execution
- Fetch specific tiles instead of entire dashboard
- Implement client-side caching
- Consider using the summary endpoint for metadata-only access

## Related Documentation

- [Headless API Guide](./HEADLESS_API_GUIDE.md) - Query execution and data transformations
- [PostHog Query API](https://posthog.com/docs/api/query) - Low-level query interface
- [Dashboard API](https://posthog.com/docs/api/dashboards) - Dashboard CRUD operations
- [Export System](./posthog/tasks/exports/) - Backend export infrastructure

## Support

For questions or issues:
- [PostHog Community](https://posthog.com/questions)
- [GitHub Issues](https://github.com/PostHog/posthog/issues)
- [API Documentation](https://posthog.com/docs/api)
