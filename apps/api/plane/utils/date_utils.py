# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from datetime import datetime, timedelta, date
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from typing import Dict, Optional, List, Union, Tuple, Any

from plane.db.models import TeamspaceProject, User

GRANULARITIES = ("day", "week", "month")


def get_analytics_date_range(
    date_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[Dict[str, Dict[str, datetime]]]:
    """
    Get date range for analytics with current and previous periods for comparison.
    Returns a dictionary with current and previous date ranges.

    Args:
        date_filter (str): The type of date filter to apply
        start_date (str): Start date for custom range (format: YYYY-MM-DD)
        end_date (str): End date for custom range (format: YYYY-MM-DD)

    Returns:
        dict: Dictionary containing current and previous date ranges
    """
    if not date_filter:
        return None

    today = timezone.now().date()

    if date_filter == "yesterday":
        yesterday = today - timedelta(days=1)
        return {
            "current": {
                "gte": datetime.combine(yesterday, datetime.min.time()),
                "lte": datetime.combine(yesterday, datetime.max.time()),
            }
        }
    elif date_filter == "last_7_days":
        return {
            "current": {
                "gte": datetime.combine(today - timedelta(days=7), datetime.min.time()),
                "lte": datetime.combine(today, datetime.max.time()),
            },
            "previous": {
                "gte": datetime.combine(today - timedelta(days=14), datetime.min.time()),
                "lte": datetime.combine(today - timedelta(days=8), datetime.max.time()),
            },
        }
    elif date_filter == "last_30_days":
        return {
            "current": {
                "gte": datetime.combine(today - timedelta(days=30), datetime.min.time()),
                "lte": datetime.combine(today, datetime.max.time()),
            },
            "previous": {
                "gte": datetime.combine(today - timedelta(days=60), datetime.min.time()),
                "lte": datetime.combine(today - timedelta(days=31), datetime.max.time()),
            },
        }
    elif date_filter == "last_3_months":
        return {
            "current": {
                "gte": datetime.combine(today - timedelta(days=90), datetime.min.time()),
                "lte": datetime.combine(today, datetime.max.time()),
            },
            "previous": {
                "gte": datetime.combine(today - timedelta(days=180), datetime.min.time()),
                "lte": datetime.combine(today - timedelta(days=91), datetime.max.time()),
            },
        }
    elif date_filter == "custom" and start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            return {
                "current": {
                    "gte": datetime.combine(start, datetime.min.time()),
                    "lte": datetime.combine(end, datetime.max.time()),
                }
            }
        except (ValueError, TypeError):
            return None
    return None


def get_chart_period_range(
    date_filter: Optional[str] = None,
) -> Optional[Tuple[date, date]]:
    """
    Get date range for chart visualization.
    Returns a tuple of (start_date, end_date) for the specified period.

    Args:
        date_filter (str): The type of date filter to apply. Options are:
            - "yesterday": Yesterday's date
            - "last_7_days": Last 7 days
            - "last_30_days": Last 30 days
            - "last_3_months": Last 90 days
            Defaults to "last_7_days" if not specified or invalid.

    Returns:
        tuple: A tuple containing (start_date, end_date) as date objects
    """
    if not date_filter:
        return None

    today = timezone.now().date()
    period_ranges = {
        "yesterday": (
            today - timedelta(days=1),
            today - timedelta(days=1),
        ),
        "last_7_days": (today - timedelta(days=7), today),
        "last_30_days": (today - timedelta(days=30), today),
        "last_3_months": (today - timedelta(days=90), today),
    }

    return period_ranges.get(date_filter, None)


def parse_id_list(value: Optional[Union[str, List[str]]]) -> List[str]:
    """Split a comma-separated id string, dropping blanks and anything that is not a UUID."""
    if not value:
        return []
    if isinstance(value, str):
        value = value.split(",")
    ids = []
    for item in value:
        try:
            ids.append(str(uuid.UUID(str(item).strip())))
        except ValueError:
            continue
    return ids


def get_teamspace_project_ids(slug: str, teamspace_ids: Optional[Union[str, List[str]]]) -> Optional[List[str]]:
    """
    Resolve teamspace ids to the ids of the projects linked to any of them.
    Returns None when no teamspace filter was requested, and an empty list when the
    requested teamspaces have no projects (so callers filter to nothing, not everything).
    """
    if not teamspace_ids:
        return None
    parsed_ids = parse_id_list(teamspace_ids)
    if not parsed_ids:
        return []
    return [
        str(project_id)
        for project_id in TeamspaceProject.objects.filter(
            teamspace_id__in=parsed_ids,
            teamspace__workspace__slug=slug,
            teamspace__deleted_at__isnull=True,
        )
        .values_list("project_id", flat=True)
        .distinct()
    ]


def get_granularity(value: Optional[str], default: str = "month") -> str:
    return value if value in GRANULARITIES else default


def get_trunc_function(granularity: str):
    return {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}[granularity]


def to_date(value: Union[date, datetime]) -> date:
    return value.date() if isinstance(value, datetime) else value


def align_to_bucket(value: date, granularity: str) -> date:
    """Return the start of the day/week (Monday)/month bucket containing ``value``."""
    if granularity == "week":
        return value - timedelta(days=value.weekday())
    if granularity == "month":
        return value.replace(day=1)
    return value


def next_bucket(value: date, granularity: str) -> date:
    if granularity == "day":
        return value + timedelta(days=1)
    if granularity == "week":
        return value + timedelta(weeks=1)
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def get_bucket_starts(start: date, end: date, granularity: str) -> List[date]:
    """All bucket start dates from the bucket containing ``start`` through the one containing ``end``."""
    buckets = []
    current = align_to_bucket(start, granularity)
    while current <= end:
        buckets.append(current)
        current = next_bucket(current, granularity)
    return buckets


def get_default_series_start(granularity: str, today: Optional[date] = None) -> date:
    """Default look-back for time series: 30 days, 12 weeks or 12 months (including the current bucket)."""
    today = today or timezone.now().date()
    if granularity == "day":
        return today - timedelta(days=29)
    if granularity == "week":
        return align_to_bucket(today, "week") - timedelta(weeks=11)
    start = today.replace(day=1)
    for _ in range(11):
        start = (start - timedelta(days=1)).replace(day=1)
    return start


def get_period_ranges(granularity: str, today: Optional[date] = None) -> Dict[str, Tuple[date, date]]:
    """Current and previous period (inclusive date ranges) for day/week/month comparisons."""
    today = today or timezone.now().date()
    current_start = align_to_bucket(today, granularity)
    current_end = next_bucket(current_start, granularity) - timedelta(days=1)
    previous_end = current_start - timedelta(days=1)
    previous_start = align_to_bucket(previous_end, granularity)
    return {"current": (current_start, current_end), "previous": (previous_start, previous_end)}


def get_analytics_filters(
    slug: str,
    user: User,
    type: str,
    date_filter: Optional[str] = None,
    project_ids: Optional[Union[str, List[str]]] = None,
    teamspace_ids: Optional[Union[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Get combined project and date filters for analytics endpoints

    Args:
        slug: The workspace slug
        user: The current user
        type: The type of filter ("analytics" or "chart")
        date_filter: Optional date filter string
        project_ids: Optional list of project IDs or comma-separated string of project IDs
        teamspace_ids: Optional list/comma-separated string of teamspace IDs; restricts to their projects

    Returns:
        dict: A dictionary containing:
            - base_filters: Base filters for the workspace and user
            - project_filters: Project-specific filters
            - analytics_date_range: Date range filters for analytics comparison
            - chart_period_range: Date range for chart visualization
            - project_ids: The resolved project id restriction (None means no restriction)
    """
    # Get project IDs from request
    if project_ids and isinstance(project_ids, str):
        project_ids = [str(project_id) for project_id in project_ids.split(",")]

    # Base filters for workspace and user
    base_filters = {
        "workspace__slug": slug,
        "project__project_projectmember__member": user,
        "project__project_projectmember__is_active": True,
        "project__deleted_at__isnull": True,
        "project__archived_at__isnull": True,
    }

    # Project filters
    project_filters = {
        "workspace__slug": slug,
        "project_projectmember__member": user,
        "project_projectmember__is_active": True,
        "deleted_at__isnull": True,
        "archived_at__isnull": True,
    }

    # Narrow to the projects of the requested teamspaces (intersected with explicit project ids)
    teamspace_project_ids = get_teamspace_project_ids(slug, teamspace_ids)
    if teamspace_project_ids is not None:
        if project_ids:
            allowed = set(teamspace_project_ids)
            project_ids = [project_id for project_id in project_ids if project_id in allowed]
        else:
            project_ids = teamspace_project_ids

    # Add project IDs to filters if provided (an empty list after teamspace resolution matches nothing)
    if project_ids or teamspace_project_ids is not None:
        base_filters["project_id__in"] = project_ids
        project_filters["id__in"] = project_ids
    else:
        project_ids = None

    # Initialize date range variables
    analytics_date_range = None
    chart_period_range = None

    # Get date range filters based on type
    if type == "analytics":
        analytics_date_range = get_analytics_date_range(date_filter)
    elif type == "chart":
        chart_period_range = get_chart_period_range(date_filter)

    return {
        "base_filters": base_filters,
        "project_filters": project_filters,
        "analytics_date_range": analytics_date_range,
        "chart_period_range": chart_period_range,
        "project_ids": project_ids,
    }
