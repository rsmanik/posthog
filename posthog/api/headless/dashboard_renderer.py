"""
Headless Dashboard Renderer

Provides programmatic dashboard rendering and export capabilities.

This module wraps PostHog's existing export system (posthog/tasks/exports/)
and adds headless-friendly endpoints for dashboard rendering.

Supported Export Formats:
- PNG: Dashboard screenshot (existing, via Selenium)
- JSON: Dashboard structure + data (new)
- JSON Data: Dashboard data only, no structure (new)
- PDF: Dashboard PDF export (future)
- SVG: Vector graphics export (future)

Usage:
    from posthog.api.headless.dashboard_renderer import DashboardRenderer

    renderer = DashboardRenderer(dashboard_id=123, team=team)

    # Render to PNG (uses existing export system)
    png_asset = renderer.render_to_png()

    # Get dashboard structure + data as JSON
    dashboard_json = renderer.render_to_json(include_data=True)

    # Get just the data
    dashboard_data = renderer.get_dashboard_data()
"""

from typing import Any, Literal, Optional
from datetime import timedelta

from django.utils.timezone import now

import structlog

from posthog.models import Dashboard, ExportedAsset, Team
from posthog.models.exported_asset import save_content
from posthog.hogql_queries.query_runner import get_query_runner, ExecutionMode
from posthog.schema import DashboardFilter

logger = structlog.get_logger(__name__)

ExportFormat = Literal["png", "json", "json_data"]


class DashboardRenderer:
    """
    Renders dashboards to various formats for headless consumption.

    This class provides a clean API for rendering dashboards programmatically.
    It wraps the existing export system and adds new JSON-based exports.
    """

    def __init__(
        self,
        dashboard_id: int,
        team: Team,
        filters: Optional[DashboardFilter] = None,
        width: int = 1920,
        height: Optional[int] = None,
    ):
        """
        Initialize dashboard renderer.

        Args:
            dashboard_id: ID of the dashboard to render
            team: Team the dashboard belongs to
            filters: Optional dashboard filters to apply
            width: Width for image exports (default 1920px)
            height: Height for image exports (None = auto)
        """
        self.dashboard_id = dashboard_id
        self.team = team
        self.filters = filters
        self.width = width
        self.height = height

        # Load dashboard
        try:
            self.dashboard = Dashboard.objects.get(id=dashboard_id, team=team)
        except Dashboard.DoesNotExist:
            raise ValueError(f"Dashboard {dashboard_id} not found for team {team.id}")

    def render_to_png(self, max_age_seconds: int = 3600) -> ExportedAsset:
        """
        Render dashboard to PNG using existing export system.

        This uses PostHog's existing Selenium-based screenshot system.
        The export is asynchronous and may take several seconds.

        Args:
            max_age_seconds: Maximum age of cached export to use (default 1 hour)

        Returns:
            ExportedAsset object (may not have content yet if still processing)
        """
        # Check for recent export
        cutoff = now() - timedelta(seconds=max_age_seconds)
        recent_export = ExportedAsset.objects.filter(
            dashboard=self.dashboard,
            export_format="image/png",
            created_at__gte=cutoff,
            has_content=True,
        ).first()

        if recent_export:
            logger.info(
                "dashboard_render_cache_hit",
                dashboard_id=self.dashboard_id,
                export_id=recent_export.id,
            )
            return recent_export

        # Create new export
        export = ExportedAsset.objects.create(
            team=self.team,
            dashboard=self.dashboard,
            export_format="image/png",
            export_context={
                "width": self.width,
                "height": self.height,
                "filters": self.filters.model_dump() if self.filters else None,
            },
        )

        # Trigger async export (via Celery)
        from posthog.tasks import exporter
        exporter.export_asset.delay(export.id)

        logger.info(
            "dashboard_render_started",
            dashboard_id=self.dashboard_id,
            export_id=export.id,
        )

        return export

    def render_to_json(self, include_data: bool = True, include_layout: bool = True) -> dict[str, Any]:
        """
        Render dashboard to JSON structure.

        This provides a complete JSON representation of the dashboard,
        optionally including query results data.

        Args:
            include_data: Include query results for each tile (default True)
            include_layout: Include layout information (default True)

        Returns:
            Dictionary with dashboard structure and optional data
        """
        dashboard_dict = {
            "id": self.dashboard.id,
            "name": self.dashboard.name,
            "description": self.dashboard.description,
            "pinned": self.dashboard.pinned,
            "created_at": self.dashboard.created_at.isoformat(),
            "created_by": {
                "id": self.dashboard.created_by.id,
                "email": self.dashboard.created_by.email,
            } if self.dashboard.created_by else None,
            "tags": list(self.dashboard.tagged_items.values_list("tag__name", flat=True)),
            "filters": self.dashboard.filters,
        }

        # Add tiles
        tiles_data = []
        for tile in self.dashboard.tiles.all().select_related("insight").prefetch_related("insight__tagged_items"):
            tile_dict = {
                "id": tile.id,
                "insight_id": tile.insight_id if tile.insight else None,
            }

            if include_layout:
                tile_dict["layouts"] = tile.layouts
                tile_dict["color"] = tile.color

            if tile.insight:
                tile_dict["insight"] = {
                    "id": tile.insight.id,
                    "name": tile.insight.name,
                    "description": tile.insight.description,
                    "favorited": tile.insight.favorited,
                    "filters": tile.insight.filters,
                    "query": tile.insight.query,
                    "tags": list(tile.insight.tagged_items.values_list("tag__name", flat=True)),
                }

                if include_data and tile.insight.query:
                    # Execute query to get data
                    try:
                        query_data = self._execute_tile_query(tile.insight.query)
                        tile_dict["insight"]["data"] = query_data
                    except Exception as e:
                        logger.warning(
                            "tile_query_execution_failed",
                            tile_id=tile.id,
                            insight_id=tile.insight.id,
                            error=str(e),
                        )
                        tile_dict["insight"]["data"] = {"error": str(e)}

            tiles_data.append(tile_dict)

        dashboard_dict["tiles"] = tiles_data
        dashboard_dict["tiles_count"] = len(tiles_data)

        return dashboard_dict

    def get_dashboard_data(self) -> dict[str, Any]:
        """
        Get just the data for each tile, without structure.

        This is useful when you want raw data without layout/metadata.

        Returns:
            Dictionary mapping tile IDs to their query results
        """
        data = {}

        for tile in self.dashboard.tiles.all().select_related("insight"):
            if tile.insight and tile.insight.query:
                try:
                    query_result = self._execute_tile_query(tile.insight.query)
                    data[str(tile.id)] = {
                        "insight_id": tile.insight_id,
                        "insight_name": tile.insight.name,
                        "data": query_result,
                    }
                except Exception as e:
                    logger.warning(
                        "tile_data_fetch_failed",
                        tile_id=tile.id,
                        error=str(e),
                    )
                    data[str(tile.id)] = {
                        "insight_id": tile.insight_id,
                        "insight_name": tile.insight.name,
                        "error": str(e),
                    }

        return data

    def _execute_tile_query(self, query: dict) -> dict[str, Any]:
        """Execute a query for a dashboard tile."""
        # Apply dashboard filters if provided
        if self.filters:
            # Merge dashboard filters with tile query
            # This is a simplified version - real implementation would be more sophisticated
            query = {**query, "dashboardFilters": self.filters.model_dump()}

        # Execute query
        query_runner = get_query_runner(query, self.team)
        result = query_runner.run(execution_mode=ExecutionMode.RECENT_CACHE_CALCULATE_BLOCKING_IF_STALE)

        return result.model_dump()

    def export_summary(self) -> dict[str, Any]:
        """
        Get a summary of the dashboard suitable for previews/listings.

        Returns:
            Lightweight summary without executing queries
        """
        return {
            "id": self.dashboard.id,
            "name": self.dashboard.name,
            "description": self.dashboard.description,
            "tiles_count": self.dashboard.tiles.count(),
            "created_at": self.dashboard.created_at.isoformat(),
            "updated_at": self.dashboard.last_modified_at.isoformat() if self.dashboard.last_modified_at else None,
            "tags": list(self.dashboard.tagged_items.values_list("tag__name", flat=True)),
            "is_shared": bool(self.dashboard.sharingconfiguration_set.filter(enabled=True).exists()),
        }


def render_dashboard(
    dashboard_id: int,
    team: Team,
    format: ExportFormat = "json",
    **options: Any
) -> Any:
    """
    Convenience function to render a dashboard.

    Args:
        dashboard_id: Dashboard ID to render
        team: Team object
        format: Export format ("png", "json", "json_data")
        **options: Additional options passed to renderer

    Returns:
        Rendered output (type depends on format)

    Examples:
        # PNG export
        asset = render_dashboard(123, team, format="png")

        # JSON export with data
        dashboard_json = render_dashboard(123, team, format="json")

        # Data only
        data = render_dashboard(123, team, format="json_data")
    """
    renderer = DashboardRenderer(dashboard_id, team, **options)

    if format == "png":
        return renderer.render_to_png()
    elif format == "json":
        return renderer.render_to_json()
    elif format == "json_data":
        return renderer.get_dashboard_data()
    else:
        raise ValueError(f"Unsupported format: {format}")
