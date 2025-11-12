"""
Headless API Views

Provides REST API endpoints optimized for headless/programmatic access.
These endpoints focus on data delivery without UI concerns.
"""

from typing import Any, cast
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from posthog.api.documentation import extend_schema
from posthog.api.routing import TeamAndOrgViewSetMixin
from posthog.hogql_queries.query_runner import ExecutionMode, get_query_runner
from posthog.models import Team
from posthog.schema import QuerySchemaRoot

from .transforms import (
    DataTransforms,
    simplify_trends_response,
    format_for_webhook,
)
from .dashboard_renderer import DashboardRenderer, render_dashboard


class HeadlessQueryViewSet(TeamAndOrgViewSetMixin, viewsets.ViewSet):
    """
    Headless Query API

    Provides simplified, headless-friendly endpoints for executing queries
    and retrieving data in various formats.

    All endpoints return pure JSON data optimized for programmatic consumption.
    """

    scope_object = "query"

    @extend_schema(
        request=QuerySchemaRoot,
        responses={200: dict},
        description="Execute a query and return results in a normalized format",
    )
    @action(methods=["POST"], detail=False)
    def execute(self, request: Request, **kwargs) -> Response:
        """
        Execute a query and return normalized results.

        This endpoint wraps the standard /api/query/ endpoint but provides
        additional normalization and simplification for headless consumers.

        Request body should contain a valid QuerySchema object.

        Returns:
            Normalized query response with consistent structure
        """
        team = cast(Team, self.team)
        query_json = request.data

        # Execute the query using PostHog's query runner
        query_runner = get_query_runner(query_json, team)

        result = query_runner.run(execution_mode=ExecutionMode.RECENT_CACHE_CALCULATE_BLOCKING_IF_STALE)

        # Normalize the response
        normalized = DataTransforms.normalize_query_response(result.model_dump())

        return Response(normalized)

    @extend_schema(
        request=QuerySchemaRoot,
        responses={200: dict},
        description="Execute a query and return simplified results optimized for trends",
    )
    @action(methods=["POST"], detail=False, url_path="execute/trends")
    def execute_trends(self, request: Request, **kwargs) -> Response:
        """
        Execute a Trends query and return simplified results.

        This endpoint is optimized for Trends queries and provides
        a simplified response structure that's easier to consume.

        Returns:
            Simplified trends response
        """
        team = cast(Team, self.team)
        query_json = request.data

        query_runner = get_query_runner(query_json, team)
        result = query_runner.run(execution_mode=ExecutionMode.RECENT_CACHE_CALCULATE_BLOCKING_IF_STALE)

        # Simplify for trends
        simplified = simplify_trends_response(result.model_dump())

        return Response(simplified)

    @extend_schema(
        request=QuerySchemaRoot,
        responses={200: str},
        description="Execute a query and return results in CSV format",
    )
    @action(methods=["POST"], detail=False, url_path="execute/csv")
    def execute_csv(self, request: Request, **kwargs) -> Response:
        """
        Execute a query and return results as CSV.

        Useful for exports, reports, and data analysis tools.

        Returns:
            CSV-formatted string
        """
        team = cast(Team, self.team)
        query_json = request.data

        query_runner = get_query_runner(query_json, team)
        result = query_runner.run(execution_mode=ExecutionMode.RECENT_CACHE_CALCULATE_BLOCKING_IF_STALE)

        # Convert to CSV
        results = result.model_dump().get("results", [])
        csv_data = DataTransforms.convert_to_csv_format(results)

        return Response(
            csv_data,
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="posthog_export.csv"'
            }
        )

    @extend_schema(
        request=QuerySchemaRoot,
        responses={200: dict},
        description="Execute a query and return results formatted for webhook delivery",
    )
    @action(methods=["POST"], detail=False, url_path="execute/webhook")
    def execute_webhook(self, request: Request, **kwargs) -> Response:
        """
        Execute a query and format results for webhook delivery.

        Provides a compact payload suitable for sending to webhooks,
        with only essential data and summary statistics.

        Returns:
            Webhook-formatted response
        """
        team = cast(Team, self.team)
        query_json = request.data

        query_runner = get_query_runner(query_json, team)
        result = query_runner.run(execution_mode=ExecutionMode.RECENT_CACHE_CALCULATE_BLOCKING_IF_STALE)

        # Format for webhook
        webhook_payload = format_for_webhook(result.model_dump())

        return Response(webhook_payload)

    @extend_schema(
        request=dict,
        responses={200: dict},
        description="Transform query results using various transformation functions",
    )
    @action(methods=["POST"], detail=False, url_path="transform")
    def transform(self, request: Request, **kwargs) -> Response:
        """
        Apply transformations to query results.

        This endpoint allows you to apply various transformations to
        already-fetched query results without re-executing the query.

        Request body should contain:
        - results: The results to transform
        - transform: The transformation to apply (flatten, pivot, summary, etc.)
        - options: Optional transformation-specific options

        Returns:
            Transformed results
        """
        results = request.data.get("results", [])
        transform_type = request.data.get("transform")
        options = request.data.get("options", {})

        transforms = DataTransforms()

        if transform_type == "flatten":
            transformed = transforms.flatten_breakdown_results(results)
        elif transform_type == "pivot":
            transformed = transforms.pivot_breakdown_data(
                results,
                row_field=options.get("row_field", "date"),
                column_field=options.get("column_field", "breakdown"),
                value_field=options.get("value_field", "value"),
            )
        elif transform_type == "summary":
            transformed = transforms.extract_summary_statistics(
                results,
                value_field=options.get("value_field", "value"),
            )
        elif transform_type == "aggregate":
            transformed = transforms.aggregate_by_time_period(
                results,
                time_field=options.get("time_field", "date"),
                value_field=options.get("value_field", "value"),
                aggregation=options.get("aggregation", "sum"),
            )
        elif transform_type == "percent_change":
            current = request.data.get("current", [])
            previous = request.data.get("previous", [])
            transformed = transforms.calculate_percent_change(
                current,
                previous,
                value_field=options.get("value_field", "value"),
            )
        elif transform_type == "csv":
            transformed = transforms.convert_to_csv_format(
                results,
                columns=options.get("columns"),
            )
        else:
            return Response(
                {"error": f"Unknown transform type: {transform_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "transform": transform_type,
            "result": transformed,
            "input_count": len(results),
        })


class HeadlessDashboardViewSet(TeamAndOrgViewSetMixin, viewsets.ViewSet):
    """
    Headless Dashboard Rendering API

    Provides endpoints for rendering dashboards programmatically
    in various formats (PNG, JSON, data-only).
    """

    scope_object = "dashboard"

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["png", "json", "json_data"], "default": "json"},
                    "filters": {"type": "object"},
                    "width": {"type": "integer", "default": 1920},
                    "height": {"type": "integer"},
                    "max_age_seconds": {"type": "integer", "default": 3600},
                    "include_data": {"type": "boolean", "default": True},
                    "include_layout": {"type": "boolean", "default": True},
                },
            }
        },
        responses={200: dict},
        description="Render dashboard in specified format",
    )
    @action(methods=["POST"], detail=True, url_path="render")
    def render(self, request: Request, pk: int, **kwargs) -> Response:
        """
        Render a dashboard in the specified format.

        This is a convenience endpoint that auto-detects the desired format
        and delegates to the appropriate renderer.

        Request body:
            - format: "png", "json", or "json_data" (default: "json")
            - filters: Optional dashboard filters to apply
            - width: Width for image exports (default: 1920px)
            - height: Height for image exports (optional)
            - max_age_seconds: Maximum age of cached PNG export (default: 3600)
            - include_data: Include query data in JSON export (default: True)
            - include_layout: Include layout info in JSON export (default: True)

        Returns:
            Rendered dashboard in requested format
        """
        team = cast(Team, self.team)
        format_type = request.data.get("format", "json")
        filters = request.data.get("filters")
        width = request.data.get("width", 1920)
        height = request.data.get("height")

        renderer = DashboardRenderer(
            dashboard_id=pk,
            team=team,
            filters=filters,
            width=width,
            height=height,
        )

        if format_type == "png":
            max_age = request.data.get("max_age_seconds", 3600)
            export = renderer.render_to_png(max_age_seconds=max_age)

            return Response({
                "export_id": export.id,
                "status": "processing" if not export.has_content else "complete",
                "url": f"/api/projects/{team.id}/exported_assets/{export.id}/content" if export.has_content else None,
                "created_at": export.created_at.isoformat(),
            })

        elif format_type == "json":
            include_data = request.data.get("include_data", True)
            include_layout = request.data.get("include_layout", True)
            dashboard_json = renderer.render_to_json(
                include_data=include_data,
                include_layout=include_layout,
            )
            return Response(dashboard_json)

        elif format_type == "json_data":
            dashboard_data = renderer.get_dashboard_data()
            return Response(dashboard_data)

        else:
            return Response(
                {"error": f"Unsupported format: {format_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object"},
                    "width": {"type": "integer", "default": 1920},
                    "height": {"type": "integer"},
                    "max_age_seconds": {"type": "integer", "default": 3600},
                },
            }
        },
        responses={200: dict},
        description="Render dashboard as PNG image",
    )
    @action(methods=["POST"], detail=True, url_path="render/png")
    def render_png(self, request: Request, pk: int, **kwargs) -> Response:
        """
        Render a dashboard as PNG image.

        This uses PostHog's existing Selenium-based screenshot system.
        The export is asynchronous and may take several seconds to complete.

        Request body:
            - filters: Optional dashboard filters to apply
            - width: Width in pixels (default: 1920)
            - height: Height in pixels (optional, auto-calculated if not provided)
            - max_age_seconds: Maximum age of cached export to use (default: 3600)

        Returns:
            Export metadata with status and URL when complete
        """
        team = cast(Team, self.team)
        filters = request.data.get("filters")
        width = request.data.get("width", 1920)
        height = request.data.get("height")
        max_age = request.data.get("max_age_seconds", 3600)

        renderer = DashboardRenderer(
            dashboard_id=pk,
            team=team,
            filters=filters,
            width=width,
            height=height,
        )

        export = renderer.render_to_png(max_age_seconds=max_age)

        return Response({
            "export_id": export.id,
            "status": "processing" if not export.has_content else "complete",
            "url": f"/api/projects/{team.id}/exported_assets/{export.id}/content" if export.has_content else None,
            "created_at": export.created_at.isoformat(),
            "dashboard_id": pk,
        })

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object"},
                    "include_data": {"type": "boolean", "default": True},
                    "include_layout": {"type": "boolean", "default": True},
                },
            }
        },
        responses={200: dict},
        description="Render dashboard as JSON with structure and data",
    )
    @action(methods=["POST"], detail=True, url_path="render/json")
    def render_json(self, request: Request, pk: int, **kwargs) -> Response:
        """
        Render a dashboard as JSON structure.

        This provides a complete JSON representation of the dashboard,
        including metadata, layout, and optionally query results data.

        Request body:
            - filters: Optional dashboard filters to apply
            - include_data: Include query results for each tile (default: True)
            - include_layout: Include layout information (default: True)

        Returns:
            Complete dashboard structure as JSON
        """
        team = cast(Team, self.team)
        filters = request.data.get("filters")
        include_data = request.data.get("include_data", True)
        include_layout = request.data.get("include_layout", True)

        renderer = DashboardRenderer(
            dashboard_id=pk,
            team=team,
            filters=filters,
        )

        dashboard_json = renderer.render_to_json(
            include_data=include_data,
            include_layout=include_layout,
        )

        return Response(dashboard_json)

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "filters": {"type": "object"},
                },
            }
        },
        responses={200: dict},
        description="Get dashboard data only (no structure)",
    )
    @action(methods=["POST"], detail=True, url_path="render/data")
    def render_data(self, request: Request, pk: int, **kwargs) -> Response:
        """
        Get just the data for each dashboard tile.

        This is useful when you want raw query results without
        layout, metadata, or other structural information.

        Request body:
            - filters: Optional dashboard filters to apply

        Returns:
            Dictionary mapping tile IDs to their query results
        """
        team = cast(Team, self.team)
        filters = request.data.get("filters")

        renderer = DashboardRenderer(
            dashboard_id=pk,
            team=team,
            filters=filters,
        )

        dashboard_data = renderer.get_dashboard_data()

        return Response(dashboard_data)

    @extend_schema(
        responses={200: dict},
        description="Get dashboard summary without executing queries",
    )
    @action(methods=["GET"], detail=True, url_path="summary")
    def summary(self, request: Request, pk: int, **kwargs) -> Response:
        """
        Get a lightweight summary of the dashboard.

        This provides dashboard metadata and structure without
        executing any queries, making it fast and suitable for
        previews and listings.

        Returns:
            Dashboard summary with metadata
        """
        team = cast(Team, self.team)

        renderer = DashboardRenderer(
            dashboard_id=pk,
            team=team,
        )

        summary_data = renderer.export_summary()

        return Response(summary_data)


class HeadlessDataViewSet(TeamAndOrgViewSetMixin, viewsets.ViewSet):
    """
    Headless Data Access API

    Provides simplified endpoints for common data access patterns
    without requiring complex query construction.
    """

    scope_object = "INTERNAL"  # TODO: Update when scope is defined

    @extend_schema(
        responses={200: dict},
        description="Get summary statistics for a date range",
    )
    @action(methods=["GET"], detail=False, url_path="summary")
    def summary(self, request: Request, **kwargs) -> Response:
        """
        Get summary statistics for the current team.

        Returns high-level metrics like total events, unique users, etc.

        Query Parameters:
            - date_from: Start date (ISO format)
            - date_to: End date (ISO format)

        Returns:
            Summary statistics
        """
        # This is a placeholder - implement based on requirements
        return Response({
            "message": "Summary endpoint - implement based on requirements",
            "date_from": request.query_params.get("date_from"),
            "date_to": request.query_params.get("date_to"),
        })

    @extend_schema(
        responses={200: dict},
        description="Health check for headless API",
    )
    @action(methods=["GET"], detail=False, url_path="health")
    def health(self, request: Request, **kwargs) -> Response:
        """
        Health check endpoint for monitoring.

        Returns:
            Health status
        """
        return Response({
            "status": "healthy",
            "version": "1.0.0",
            "features": [
                "query_execution",
                "data_transforms",
                "csv_export",
                "webhook_format",
            ],
        })
