"""
Data Transformation Utilities for Headless API

This module provides pure data transformation functions that can be used
by any client (web, mobile, CLI, etc.) to process PostHog query results
into various formats.

All functions are pure (no side effects) and operate on dictionaries/lists
to maintain compatibility with JSON serialization.
"""

from typing import Any, Optional
from datetime import datetime, date
from decimal import Decimal


class DataTransforms:
    """
    Collection of data transformation utilities for headless API consumers.

    These transformations are UI-agnostic and can be used by any client
    that needs to process PostHog data.
    """

    @staticmethod
    def flatten_breakdown_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Flatten breakdown results into a simpler format for consumption.

        Args:
            results: List of result objects with breakdown information

        Returns:
            Flattened list where each item represents a single breakdown value

        Example:
            Input:
            [
                {
                    "label": "$pageview",
                    "breakdown_value": "Chrome",
                    "data": [10, 20, 30],
                    "days": ["2024-01-01", "2024-01-02", "2024-01-03"]
                }
            ]

            Output:
            [
                {"date": "2024-01-01", "event": "$pageview", "breakdown": "Chrome", "count": 10},
                {"date": "2024-01-02", "event": "$pageview", "breakdown": "Chrome", "count": 20},
                {"date": "2024-01-03", "event": "$pageview", "breakdown": "Chrome", "count": 30}
            ]
        """
        flattened = []

        for result in results:
            label = result.get("label", "")
            breakdown_value = result.get("breakdown_value")
            data = result.get("data", [])
            days = result.get("days", [])

            for idx, value in enumerate(data):
                day = days[idx] if idx < len(days) else None
                flattened.append({
                    "date": day,
                    "label": label,
                    "breakdown": breakdown_value,
                    "value": value,
                })

        return flattened

    @staticmethod
    def normalize_query_response(response: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize a query response to a consistent format.

        Handles different query types (Trends, Funnels, etc.) and
        provides a unified structure.

        Args:
            response: Raw query response from PostHog API

        Returns:
            Normalized response with consistent structure
        """
        kind = response.get("kind", "Unknown")
        results = response.get("results", [])

        normalized = {
            "query_type": kind,
            "results": results,
            "metadata": {
                "has_more": response.get("hasMore", False),
                "limit": response.get("limit"),
                "offset": response.get("offset"),
                "columns": response.get("columns", []),
                "types": response.get("types", []),
            }
        }

        # Add timing information if available
        if "timings" in response:
            normalized["metadata"]["timings"] = response["timings"]

        # Add date range if available
        if "dateRange" in response:
            normalized["metadata"]["date_range"] = response["dateRange"]

        return normalized

    @staticmethod
    def convert_to_csv_format(results: list[dict[str, Any]], columns: Optional[list[str]] = None) -> str:
        """
        Convert query results to CSV format.

        Args:
            results: List of result dictionaries
            columns: Optional list of column names. If not provided, uses keys from first result.

        Returns:
            CSV-formatted string
        """
        if not results:
            return ""

        # Determine columns
        if columns is None:
            columns = list(results[0].keys()) if results else []

        # Build CSV
        lines = []

        # Header
        lines.append(",".join(f'"{col}"' for col in columns))

        # Rows
        for result in results:
            row = []
            for col in columns:
                value = result.get(col, "")
                # Handle different types
                if value is None:
                    row.append("")
                elif isinstance(value, (datetime, date)):
                    row.append(f'"{value.isoformat()}"')
                elif isinstance(value, (int, float, Decimal)):
                    row.append(str(value))
                elif isinstance(value, bool):
                    row.append("true" if value else "false")
                else:
                    # Escape quotes in strings
                    str_value = str(value).replace('"', '""')
                    row.append(f'"{str_value}"')
            lines.append(",".join(row))

        return "\n".join(lines)

    @staticmethod
    def aggregate_by_time_period(
        results: list[dict[str, Any]],
        time_field: str = "date",
        value_field: str = "value",
        aggregation: str = "sum"
    ) -> dict[str, float]:
        """
        Aggregate results by time period.

        Args:
            results: List of results with time and value fields
            time_field: Name of the time field
            value_field: Name of the value field to aggregate
            aggregation: Type of aggregation ("sum", "avg", "min", "max", "count")

        Returns:
            Dictionary mapping time period to aggregated value
        """
        from collections import defaultdict

        grouped: dict[str, list[float]] = defaultdict(list)

        for result in results:
            time_key = result.get(time_field)
            value = result.get(value_field)

            if time_key and value is not None:
                grouped[str(time_key)].append(float(value))

        # Apply aggregation
        aggregated = {}
        for time_key, values in grouped.items():
            if aggregation == "sum":
                aggregated[time_key] = sum(values)
            elif aggregation == "avg":
                aggregated[time_key] = sum(values) / len(values)
            elif aggregation == "min":
                aggregated[time_key] = min(values)
            elif aggregation == "max":
                aggregated[time_key] = max(values)
            elif aggregation == "count":
                aggregated[time_key] = len(values)
            else:
                raise ValueError(f"Unknown aggregation type: {aggregation}")

        return aggregated

    @staticmethod
    def calculate_percent_change(
        current: list[dict[str, Any]],
        previous: list[dict[str, Any]],
        value_field: str = "value"
    ) -> list[dict[str, Any]]:
        """
        Calculate percent change between current and previous periods.

        Args:
            current: Current period results
            previous: Previous period results
            value_field: Field containing the value to compare

        Returns:
            Results with percent_change field added
        """
        enriched = []

        for idx, curr in enumerate(current):
            prev = previous[idx] if idx < len(previous) else None

            result = curr.copy()

            if prev:
                curr_value = float(curr.get(value_field, 0))
                prev_value = float(prev.get(value_field, 0))

                if prev_value != 0:
                    percent_change = ((curr_value - prev_value) / prev_value) * 100
                    result["percent_change"] = round(percent_change, 2)
                    result["previous_value"] = prev_value
                else:
                    result["percent_change"] = None if curr_value == 0 else float('inf')
                    result["previous_value"] = 0
            else:
                result["percent_change"] = None
                result["previous_value"] = None

            enriched.append(result)

        return enriched

    @staticmethod
    def pivot_breakdown_data(
        results: list[dict[str, Any]],
        row_field: str = "date",
        column_field: str = "breakdown",
        value_field: str = "value"
    ) -> dict[str, dict[str, Any]]:
        """
        Pivot breakdown data for easier consumption.

        Converts from long format (one row per date/breakdown combination)
        to wide format (one row per date, columns for each breakdown).

        Args:
            results: List of results in long format
            row_field: Field to use as row identifier
            column_field: Field to use for column names
            value_field: Field containing values

        Returns:
            Pivoted data structure

        Example:
            Input:
            [
                {"date": "2024-01-01", "breakdown": "Chrome", "value": 10},
                {"date": "2024-01-01", "breakdown": "Firefox", "value": 5},
                {"date": "2024-01-02", "breakdown": "Chrome", "value": 12}
            ]

            Output:
            {
                "2024-01-01": {"Chrome": 10, "Firefox": 5},
                "2024-01-02": {"Chrome": 12, "Firefox": 0}
            }
        """
        from collections import defaultdict

        pivoted: dict[str, dict[str, Any]] = defaultdict(dict)

        for result in results:
            row_key = result.get(row_field)
            column_key = result.get(column_field)
            value = result.get(value_field)

            if row_key and column_key is not None:
                pivoted[str(row_key)][str(column_key)] = value

        return dict(pivoted)

    @staticmethod
    def extract_summary_statistics(results: list[dict[str, Any]], value_field: str = "value") -> dict[str, Any]:
        """
        Calculate summary statistics for a result set.

        Args:
            results: List of results
            value_field: Field containing values to summarize

        Returns:
            Dictionary with summary statistics
        """
        values = [float(r.get(value_field, 0)) for r in results if r.get(value_field) is not None]

        if not values:
            return {
                "count": 0,
                "sum": 0,
                "mean": 0,
                "min": 0,
                "max": 0,
                "median": 0,
                "std_dev": 0,
            }

        sorted_values = sorted(values)
        n = len(values)
        mean_value = sum(values) / n

        # Calculate median
        if n % 2 == 0:
            median = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
        else:
            median = sorted_values[n // 2]

        # Calculate standard deviation
        variance = sum((x - mean_value) ** 2 for x in values) / n
        std_dev = variance ** 0.5

        return {
            "count": n,
            "sum": sum(values),
            "mean": round(mean_value, 2),
            "min": min(values),
            "max": max(values),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
        }


# Convenience functions for common transformations

def simplify_trends_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Simplify a Trends query response for headless consumption.

    Extracts the most commonly needed fields and provides a clean structure.
    """
    results = response.get("results", [])

    simplified = {
        "data": [],
        "summary": {
            "total_series": len(results),
            "date_range": response.get("dateRange"),
        }
    }

    for series in results:
        simplified["data"].append({
            "label": series.get("label"),
            "action": series.get("action"),
            "count": series.get("count", 0),
            "data": series.get("data", []),
            "labels": series.get("labels", []),
            "days": series.get("days", []),
            "breakdown_value": series.get("breakdown_value"),
        })

    return simplified


def format_for_webhook(response: dict[str, Any]) -> dict[str, Any]:
    """
    Format a response for webhook delivery.

    Removes unnecessary fields and ensures the payload is small and focused.
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "query_type": response.get("kind"),
        "results_count": len(response.get("results", [])),
        "results": response.get("results", []),
        "summary": DataTransforms.extract_summary_statistics(response.get("results", [])),
    }
