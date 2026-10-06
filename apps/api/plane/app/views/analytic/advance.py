# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date
from rest_framework.response import Response
from rest_framework import status
from typing import Dict, List, Any, Optional, Tuple
from django.db import models
from django.db.models import QuerySet, Q, Count, Sum, F, Case, When, Value
from django.db.models.functions import Cast, Coalesce, Concat, TruncDate
from django.http import HttpRequest
from django.utils import timezone
from plane.app.views.base import BaseAPIView
from plane.app.permissions import ROLE, allow_permission
from plane.db.models import (
    WorkspaceMember,
    Project,
    Issue,
    IssueAssignee,
    IssueWorklog,
    Cycle,
    Module,
    IssueView,
    ProjectPage,
    Workspace,
    ProjectMember,
    Teamspace,
    TeamspaceMember,
    TeamspaceProject,
    User,
)
from plane.utils.build_chart import build_analytics_chart, build_created_vs_resolved_series
from plane.utils.date_utils import (
    date_range_filter,
    get_analytics_filters,
    get_bucket_starts,
    get_default_series_start,
    get_granularity,
    get_period_ranges,
    get_trunc_function,
    align_to_bucket,
    parse_id_list,
    to_date,
)

PENDING_STATE_GROUPS = ["backlog", "unstarted", "started"]
CLOSED_STATE_GROUPS = ["completed", "cancelled"]
NUMERIC_VALUE_REGEX = r"^\s*[0-9]+(\.[0-9]+)?\s*$"
# Only work items carrying a time-based estimate can contribute allocated minutes; filtering on it
# first keeps the allocation aggregates from scanning every work item in the selected projects.
TIME_ESTIMATED = Q(estimate_point__estimate__type="time")


def minutes_to_hours(minutes: Optional[int]) -> float:
    return round((minutes or 0) / 60, 2)


def numeric_estimate_value(estimate_type: str, prefix: str = "estimate_point__") -> Case:
    """Numeric value of an issue's estimate point, only for estimates of ``estimate_type``."""
    return Case(
        When(
            **{
                f"{prefix}estimate__type": estimate_type,
                f"{prefix}value__regex": NUMERIC_VALUE_REGEX,
            },
            then=Cast(f"{prefix}value", models.FloatField()),
        ),
        default=None,
        output_field=models.FloatField(),
    )


def allocated_minutes(prefix: str = "") -> Case:
    """Minutes allocated to a work item through a time-based estimate (``prefix`` points at the issue)."""
    return numeric_estimate_value("time", prefix=f"{prefix}estimate_point__")


def utilization_percentage(spent_minutes: Optional[float], allocated_minutes: Optional[float]) -> Optional[float]:
    """Spent / allocated time as a percentage (1 decimal); None when nothing is allocated."""
    if not allocated_minutes:
        return None
    return round((spent_minutes or 0) * 100 / allocated_minutes, 1)


def overdue_filter(today: date) -> Q:
    return Q(target_date__lt=today) & ~Q(state__group__in=CLOSED_STATE_GROUPS)


def avatar_url_expression(prefix: str) -> Case:
    return Case(
        When(
            **{f"{prefix}avatar_asset__isnull": False},
            then=Concat(
                Value("/api/assets/v2/static/"),
                Cast(f"{prefix}avatar_asset", models.CharField()),
                Value("/"),
            ),
        ),
        When(**{f"{prefix}avatar_asset__isnull": True}, then=F(f"{prefix}avatar")),
        default=Value(None),
        output_field=models.CharField(),
    )


class AdvanceAnalyticsBaseView(BaseAPIView):
    def initialize_workspace(self, slug: str, type: str) -> None:
        self._workspace_slug = slug
        self.filters = get_analytics_filters(
            slug=slug,
            type=type,
            user=self.request.user,
            date_filter=self.request.GET.get("date_filter", None),
            project_ids=self.request.GET.get("project_ids", None),
            teamspace_ids=self.request.GET.get("teamspace_ids", None),
        )

    def get_project_ids(self) -> List[Any]:
        """Ids of the projects the user can see after project/teamspace filters, without join duplicates."""
        if not hasattr(self, "_project_ids"):
            self._project_ids = list(
                Project.objects.filter(**self.filters["project_filters"]).values_list("id", flat=True).distinct()
            )
        return self._project_ids

    def get_issue_queryset(self) -> QuerySet:
        return Issue.issue_objects.filter(project_id__in=self.get_project_ids())

    def get_worklog_queryset(self) -> QuerySet:
        return IssueWorklog.objects.filter(
            project_id__in=self.get_project_ids(),
            issue__deleted_at__isnull=True,
        )

    def get_analytics_range(self) -> Optional[Tuple[date, date]]:
        """Inclusive date range of the ``date_filter`` (analytics or chart flavour), if any."""
        if self.filters["analytics_date_range"]:
            current = self.filters["analytics_date_range"]["current"]
            return current["gte"].date(), current["lte"].date()
        return self.filters["chart_period_range"]


class AdvanceAnalyticsEndpoint(AdvanceAnalyticsBaseView):
    def get_filtered_counts(self, queryset: QuerySet) -> Dict[str, int]:
        def get_filtered_count() -> int:
            if self.filters["analytics_date_range"]:
                return queryset.filter(
                    created_at__gte=self.filters["analytics_date_range"]["current"]["gte"],
                    created_at__lte=self.filters["analytics_date_range"]["current"]["lte"],
                ).count()
            return queryset.count()

        def get_previous_count() -> int:
            if self.filters["analytics_date_range"] and self.filters["analytics_date_range"].get("previous"):
                return queryset.filter(
                    created_at__gte=self.filters["analytics_date_range"]["previous"]["gte"],
                    created_at__lte=self.filters["analytics_date_range"]["previous"]["lte"],
                ).count()
            return 0

        return {
            "count": get_filtered_count(),
            # "filter_count": get_previous_count(),
        }

    def get_overview_data(self) -> Dict[str, Dict[str, int]]:
        members_query = WorkspaceMember.objects.filter(
            workspace__slug=self._workspace_slug, is_active=True, member__is_bot=False
        )

        if self.filters["project_ids"] is not None:
            members_query = ProjectMember.objects.filter(
                project_id__in=self.filters["project_ids"], is_active=True, member__is_bot=False
            )

        return {
            "total_users": self.get_filtered_counts(members_query),
            "total_admins": self.get_filtered_counts(members_query.filter(role=ROLE.ADMIN.value)),
            "total_members": self.get_filtered_counts(members_query.filter(role=ROLE.MEMBER.value)),
            "total_guests": self.get_filtered_counts(members_query.filter(role=ROLE.GUEST.value)),
            "total_projects": self.get_filtered_counts(Project.objects.filter(**self.filters["project_filters"])),
            "total_work_items": self.get_filtered_counts(Issue.issue_objects.filter(**self.filters["base_filters"])),
            "total_cycles": self.get_filtered_counts(Cycle.objects.filter(**self.filters["base_filters"])),
            "total_intake": self.get_filtered_counts(
                Issue.objects.filter(**self.filters["base_filters"]).filter(
                    issue_intake__status__in=["-2", "-1", "0", "1", "2"]  # TODO: Add description for reference.
                )
            ),
        }

    def get_work_items_stats(self) -> Dict[str, Dict[str, int]]:
        base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"])

        return {
            "total_work_items": self.get_filtered_counts(base_queryset),
            "started_work_items": self.get_filtered_counts(base_queryset.filter(state__group="started")),
            "backlog_work_items": self.get_filtered_counts(base_queryset.filter(state__group="backlog")),
            "un_started_work_items": self.get_filtered_counts(base_queryset.filter(state__group="unstarted")),
            "completed_work_items": self.get_filtered_counts(base_queryset.filter(state__group="completed")),
        }

    def filter_by_date(self, queryset: QuerySet, field: str) -> QuerySet:
        date_range = self.get_analytics_range()
        if not date_range:
            return queryset
        return queryset.filter(**date_range_filter(field, date_range[0], date_range[1]))

    def get_projects_data(self) -> Dict[str, Dict[str, Any]]:
        today = timezone.localdate()
        project_ids = self.get_project_ids()
        issues = self.filter_by_date(self.get_issue_queryset(), "created_at__date")
        issue_counts = issues.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(state__group="completed")),
            overdue=Count("id", filter=overdue_filter(today)),
        )
        total_members = (
            ProjectMember.objects.filter(project_id__in=project_ids, is_active=True, member__is_bot=False)
            .values("member_id")
            .distinct()
            .count()
        )
        logged_minutes = self.filter_by_date(self.get_worklog_queryset(), "logged_at").aggregate(total=Sum("duration"))[
            "total"
        ]
        return {
            "total_projects": {"count": len(project_ids)},
            "total_work_items": {"count": issue_counts["total"]},
            "completed_work_items": {"count": issue_counts["completed"]},
            "overdue_work_items": {"count": issue_counts["overdue"]},
            "total_members": {"count": total_members},
            "total_time_logged": {"count": minutes_to_hours(logged_minutes)},
        }

    def get_time_tracking_data(self) -> Dict[str, Dict[str, Any]]:
        worklogs = self.get_worklog_queryset()
        weeks = get_period_ranges("week")
        filtered_worklogs = self.filter_by_date(worklogs, "logged_at")
        totals = filtered_worklogs.aggregate(
            total=Sum("duration"),
            contributors=Count("logged_by_id", distinct=True),
        )
        week_totals = worklogs.aggregate(
            this_week=Sum("duration", filter=Q(logged_at__range=weeks["current"])),
            last_week=Sum("duration", filter=Q(logged_at__range=weeks["previous"])),
        )
        # Time-based estimates store their value in minutes.
        estimated_minutes = self.filter_by_date(
            self.get_issue_queryset().filter(TIME_ESTIMATED), "created_at__date"
        ).aggregate(total=Sum(allocated_minutes()))["total"]
        return {
            "total_time_logged": {"count": minutes_to_hours(totals["total"])},
            "time_logged_this_week": {"count": minutes_to_hours(week_totals["this_week"])},
            "time_logged_last_week": {"count": minutes_to_hours(week_totals["last_week"])},
            "total_estimated_time": {"count": minutes_to_hours(estimated_minutes)},
            "contributors": {"count": totals["contributors"]},
            "utilization_percentage": {"count": utilization_percentage(totals["total"], estimated_minutes) or 0},
        }

    def get_progress_data(self) -> Dict[str, Dict[str, Any]]:
        granularity = get_granularity(self.request.GET.get("granularity"), default="week")
        periods = get_period_ranges(granularity)
        issues = self.get_issue_queryset()
        worklogs = self.get_worklog_queryset()

        current, previous = periods["current"], periods["previous"]
        # previous always precedes current, so one range covers both periods
        full_range = (previous[0], current[1])

        def in_period(field: str, period: Tuple[date, date]) -> Q:
            return Q(**date_range_filter(field, *period))

        created = issues.filter(in_period("created_at__date", full_range)).aggregate(
            current=Count("id", filter=in_period("created_at__date", current)),
            previous=Count("id", filter=in_period("created_at__date", previous)),
        )
        completed = issues.filter(in_period("completed_at__date", full_range), state__group="completed").aggregate(
            current=Count("id", filter=in_period("completed_at__date", current)),
            previous=Count("id", filter=in_period("completed_at__date", previous)),
        )
        # Contributors are the people who logged time in the period, not anyone who touched a work item.
        logged = worklogs.filter(in_period("logged_at", full_range)).aggregate(
            current=Sum("duration", filter=in_period("logged_at", current)),
            previous=Sum("duration", filter=in_period("logged_at", previous)),
            current_contributors=Count("logged_by_id", distinct=True, filter=in_period("logged_at", current)),
            previous_contributors=Count("logged_by_id", distinct=True, filter=in_period("logged_at", previous)),
        )

        return {
            "created_work_items": {"count": created["current"], "previous_count": created["previous"]},
            "completed_work_items": {"count": completed["current"], "previous_count": completed["previous"]},
            "time_logged": {
                "count": minutes_to_hours(logged["current"]),
                "previous_count": minutes_to_hours(logged["previous"]),
            },
            "active_contributors": {
                "count": logged["current_contributors"],
                "previous_count": logged["previous_contributors"],
            },
        }

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request: HttpRequest, slug: str) -> Response:
        self.initialize_workspace(slug, type="analytics")
        tab = request.GET.get("tab", "overview")

        if tab == "overview":
            return Response(
                self.get_overview_data(),
                status=status.HTTP_200_OK,
            )
        elif tab == "work-items":
            return Response(
                self.get_work_items_stats(),
                status=status.HTTP_200_OK,
            )
        elif tab == "projects":
            return Response(self.get_projects_data(), status=status.HTTP_200_OK)
        elif tab == "time-tracking":
            return Response(self.get_time_tracking_data(), status=status.HTTP_200_OK)
        elif tab == "progress":
            return Response(self.get_progress_data(), status=status.HTTP_200_OK)
        return Response({"message": "Invalid tab"}, status=status.HTTP_400_BAD_REQUEST)


class AdvanceAnalyticsStatsEndpoint(AdvanceAnalyticsBaseView):
    def get_project_issues_stats(self) -> QuerySet:
        # Get the base queryset with workspace and project filters
        base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"])

        # Apply date range filter if available
        if self.filters["chart_period_range"]:
            start_date, end_date = self.filters["chart_period_range"]
            base_queryset = base_queryset.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

        return (
            base_queryset.values("project_id", "project__name")
            .annotate(
                cancelled_work_items=Count("id", filter=Q(state__group="cancelled")),
                completed_work_items=Count("id", filter=Q(state__group="completed")),
                backlog_work_items=Count("id", filter=Q(state__group="backlog")),
                un_started_work_items=Count("id", filter=Q(state__group="unstarted")),
                started_work_items=Count("id", filter=Q(state__group="started")),
            )
            .order_by("project_id")
        )

    def get_work_items_stats(self) -> Dict[str, Dict[str, int]]:
        base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"])
        return (
            base_queryset.values("project_id", "project__name")
            .annotate(
                cancelled_work_items=Count("id", filter=Q(state__group="cancelled")),
                completed_work_items=Count("id", filter=Q(state__group="completed")),
                backlog_work_items=Count("id", filter=Q(state__group="backlog")),
                un_started_work_items=Count("id", filter=Q(state__group="unstarted")),
                started_work_items=Count("id", filter=Q(state__group="started")),
            )
            .order_by("project_id")
        )

    def filter_by_chart_period(self, queryset: QuerySet, field: str) -> QuerySet:
        if not self.filters["chart_period_range"]:
            return queryset
        start_date, end_date = self.filters["chart_period_range"]
        return queryset.filter(**date_range_filter(field, start_date, end_date))

    def get_projects_stats(self) -> List[Dict[str, Any]]:
        today = timezone.localdate()
        project_ids = self.get_project_ids()
        projects = Project.objects.filter(id__in=project_ids).values("id", "name").order_by("name")

        issue_stats = {
            row["project_id"]: row
            for row in self.filter_by_chart_period(self.get_issue_queryset(), "created_at__date")
            .values("project_id")
            .annotate(
                total_work_items=Count("id"),
                completed_work_items=Count("id", filter=Q(state__group="completed")),
                cancelled_work_items=Count("id", filter=Q(state__group="cancelled")),
                pending_work_items=Count("id", filter=Q(state__group__in=PENDING_STATE_GROUPS)),
                overdue_work_items=Count("id", filter=overdue_filter(today)),
                estimate_points=Sum(numeric_estimate_value("points")),
                allocated_minutes=Sum(allocated_minutes()),
            )
            .order_by()
        }

        def count_by_project(queryset: QuerySet, field: str = "id") -> Dict[Any, int]:
            return {
                row["project_id"]: row["total"]
                for row in queryset.values("project_id").annotate(total=Count(field, distinct=True)).order_by()
            }

        member_counts = count_by_project(
            ProjectMember.objects.filter(project_id__in=project_ids, is_active=True, member__is_bot=False),
            "member_id",
        )
        cycle_counts = count_by_project(Cycle.objects.filter(project_id__in=project_ids))
        module_counts = count_by_project(Module.objects.filter(project_id__in=project_ids))
        logged_minutes = {
            row["project_id"]: row["total"]
            for row in self.filter_by_chart_period(self.get_worklog_queryset(), "logged_at")
            .values("project_id")
            .annotate(total=Sum("duration"))
            .order_by()
        }
        teamspace_ids: Dict[Any, List[str]] = {}
        for project_id, teamspace_id in TeamspaceProject.objects.filter(
            project_id__in=project_ids, teamspace__deleted_at__isnull=True
        ).values_list("project_id", "teamspace_id"):
            teamspace_ids.setdefault(project_id, []).append(str(teamspace_id))

        rows = []
        for project in projects:
            stats = issue_stats.get(project["id"], {})
            total = stats.get("total_work_items", 0)
            completed = stats.get("completed_work_items", 0)
            cancelled = stats.get("cancelled_work_items", 0)
            estimate_points = stats.get("estimate_points")
            rows.append(
                {
                    "project_id": str(project["id"]),
                    "project__name": project["name"],
                    "total_work_items": total,
                    "completed_work_items": completed,
                    "pending_work_items": stats.get("pending_work_items", 0),
                    "cancelled_work_items": cancelled,
                    "overdue_work_items": stats.get("overdue_work_items", 0),
                    "completion_percentage": (
                        round(completed * 100 / (total - cancelled), 1) if total - cancelled > 0 else 0.0
                    ),
                    "total_members": member_counts.get(project["id"], 0),
                    "total_cycles": cycle_counts.get(project["id"], 0),
                    "total_modules": module_counts.get(project["id"], 0),
                    "estimate_points": round(estimate_points, 2) if estimate_points is not None else None,
                    "time_logged": minutes_to_hours(logged_minutes.get(project["id"])),
                    "estimated_time": minutes_to_hours(stats.get("allocated_minutes")),
                    "utilization_percentage": utilization_percentage(
                        logged_minutes.get(project["id"]), stats.get("allocated_minutes")
                    ),
                    "teamspace_ids": teamspace_ids.get(project["id"], []),
                }
            )
        return rows

    def get_time_tracking_stats(self) -> List[Dict[str, Any]]:
        logged_rows = (
            self.filter_by_chart_period(self.get_worklog_queryset(), "logged_at")
            .values("project_id", "logged_by_id")
            .annotate(minutes=Sum("duration"), work_items_logged=Count("issue_id", distinct=True))
            .order_by()
        )
        # An item with several assignees counts fully towards each of them.
        allocated_rows = (
            self.filter_by_chart_period(
                IssueAssignee.objects.filter(
                    project_id__in=self.get_project_ids(),
                    issue__in=self.get_issue_queryset().filter(TIME_ESTIMATED),
                ),
                "issue__created_at__date",
            )
            .values("project_id", "assignee_id")
            .annotate(minutes=Sum(allocated_minutes("issue__")))
            .filter(minutes__gt=0)
            .order_by()
        )

        stats: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
        for row in logged_rows:
            stats[(row["project_id"], row["logged_by_id"])] = {
                "logged": row["minutes"],
                "work_items_logged": row["work_items_logged"],
            }
        for row in allocated_rows:
            stats.setdefault((row["project_id"], row["assignee_id"]), {})["allocated"] = row["minutes"]

        project_names = dict(
            Project.objects.filter(id__in={project_id for project_id, _ in stats}).values_list("id", "name")
        )
        members = {
            member["id"]: member
            for member in User.objects.filter(id__in={member_id for _, member_id in stats})
            .annotate(avatar_url=avatar_url_expression(""))
            .values("id", "display_name", "avatar_url")
        }

        rows = []
        for (project_id, member_id), values in stats.items():
            member = members.get(member_id, {})
            rows.append(
                {
                    "project_id": str(project_id),
                    "project__name": project_names.get(project_id),
                    "member_id": str(member_id),
                    "display_name": member.get("display_name"),
                    "avatar_url": member.get("avatar_url"),
                    "time_logged": minutes_to_hours(values.get("logged")),
                    "estimated_time": minutes_to_hours(values.get("allocated")),
                    "work_items_logged": values.get("work_items_logged", 0),
                }
            )
        rows.sort(key=lambda row: (-row["time_logged"], -row["estimated_time"], row["project__name"] or ""))
        return rows

    def get_teamspaces_stats(self) -> List[Dict[str, Any]]:
        """Resource distribution per teamspace, over the projects visible after the project/teamspace filters."""
        project_ids = self.get_project_ids()
        teamspaces = Teamspace.objects.filter(workspace__slug=self._workspace_slug)
        requested_teamspace_ids = self.request.GET.get("teamspace_ids")
        if requested_teamspace_ids:
            teamspaces = teamspaces.filter(id__in=parse_id_list(requested_teamspace_ids))
        teamspaces = list(teamspaces.values("id", "name").order_by("name"))
        teamspace_ids = [teamspace["id"] for teamspace in teamspaces]

        projects_by_teamspace: Dict[Any, List[Any]] = {}
        for teamspace_id, project_id in TeamspaceProject.objects.filter(
            teamspace_id__in=teamspace_ids, project_id__in=project_ids
        ).values_list("teamspace_id", "project_id"):
            projects_by_teamspace.setdefault(teamspace_id, []).append(project_id)

        member_counts = dict(
            TeamspaceMember.objects.filter(teamspace_id__in=teamspace_ids, member__is_bot=False)
            .values("teamspace_id")
            .annotate(total=Count("member_id", distinct=True))
            .order_by()
            .values_list("teamspace_id", "total")
        )

        # Aggregate once per project, then roll projects up into their teamspaces in Python:
        # a project can belong to several teamspaces, so joining teamspaces in SQL would double count.
        linked_project_ids = {project_id for ids in projects_by_teamspace.values() for project_id in ids}
        issue_stats = {
            row["project_id"]: row
            for row in self.filter_by_chart_period(
                self.get_issue_queryset().filter(project_id__in=linked_project_ids), "created_at__date"
            )
            .values("project_id")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(state__group="completed")),
                pending=Count("id", filter=Q(state__group__in=PENDING_STATE_GROUPS)),
                allocated=Sum(allocated_minutes()),
            )
            .order_by()
        }
        logged_minutes = dict(
            self.filter_by_chart_period(
                self.get_worklog_queryset().filter(project_id__in=linked_project_ids), "logged_at"
            )
            .values("project_id")
            .annotate(total=Sum("duration"))
            .order_by()
            .values_list("project_id", "total")
        )

        rows = []
        for teamspace in teamspaces:
            teamspace_project_ids = projects_by_teamspace.get(teamspace["id"], [])
            project_stats = [issue_stats.get(project_id, {}) for project_id in teamspace_project_ids]
            allocated = sum(stat.get("allocated") or 0 for stat in project_stats)
            logged = sum(logged_minutes.get(project_id) or 0 for project_id in teamspace_project_ids)
            rows.append(
                {
                    "teamspace_id": str(teamspace["id"]),
                    "name": teamspace["name"],
                    "total_projects": len(teamspace_project_ids),
                    "total_members": member_counts.get(teamspace["id"], 0),
                    "total_work_items": sum(stat.get("total", 0) for stat in project_stats),
                    "completed_work_items": sum(stat.get("completed", 0) for stat in project_stats),
                    "pending_work_items": sum(stat.get("pending", 0) for stat in project_stats),
                    "estimated_time": minutes_to_hours(allocated),
                    "time_logged": minutes_to_hours(logged),
                    "utilization_percentage": utilization_percentage(logged, allocated),
                }
            )
        return rows

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request: HttpRequest, slug: str) -> Response:
        self.initialize_workspace(slug, type="chart")
        type = request.GET.get("type", "work-items")

        if type == "work-items":
            return Response(
                self.get_work_items_stats(),
                status=status.HTTP_200_OK,
            )
        elif type == "projects":
            return Response(self.get_projects_stats(), status=status.HTTP_200_OK)
        elif type == "time-tracking":
            return Response(self.get_time_tracking_stats(), status=status.HTTP_200_OK)
        elif type == "teamspaces":
            return Response(self.get_teamspaces_stats(), status=status.HTTP_200_OK)

        return Response({"message": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)


class AdvanceAnalyticsChartEndpoint(AdvanceAnalyticsBaseView):
    def project_chart(self) -> List[Dict[str, Any]]:
        # Get the base queryset with workspace and project filters
        base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"])
        date_filter = {}

        # Apply date range filter if available
        if self.filters["chart_period_range"]:
            start_date, end_date = self.filters["chart_period_range"]
            date_filter = {
                "created_at__date__gte": start_date,
                "created_at__date__lte": end_date,
            }

        total_work_items = base_queryset.filter(**date_filter).count()
        total_cycles = Cycle.objects.filter(**self.filters["base_filters"], **date_filter).count()
        total_modules = Module.objects.filter(**self.filters["base_filters"], **date_filter).count()
        total_intake = Issue.objects.filter(
            issue_intake__isnull=False, **self.filters["base_filters"], **date_filter
        ).count()
        total_members = WorkspaceMember.objects.filter(
            workspace__slug=self._workspace_slug, is_active=True, **date_filter
        ).count()
        total_pages = ProjectPage.objects.filter(**self.filters["base_filters"], **date_filter).count()
        total_views = IssueView.objects.filter(**self.filters["base_filters"], **date_filter).count()

        data = {
            "work_items": total_work_items,
            "cycles": total_cycles,
            "modules": total_modules,
            "intake": total_intake,
            "members": total_members,
            "pages": total_pages,
            "views": total_views,
        }

        return [
            {
                "key": key,
                "name": key.replace("_", " ").title(),
                "count": value or 0,
            }
            for key, value in data.items()
        ]

    def get_series_range(self, granularity: str, default_start: date) -> Tuple[date, date]:
        """Start/end dates of a time series: the ``date_filter`` period if given, else the default look-back."""
        if self.filters["chart_period_range"]:
            return self.filters["chart_period_range"]
        return default_start, timezone.localdate()

    def work_item_completion_chart(self) -> Dict[str, Any]:
        granularity = get_granularity(self.request.GET.get("granularity"))
        queryset = Issue.issue_objects.filter(**self.filters["base_filters"])

        if granularity == "month":
            workspace = Workspace.objects.get(slug=self._workspace_slug)
            default_start = workspace.created_at.date().replace(day=1)
        else:
            default_start = get_default_series_start(granularity)
        start_date, end_date = self.get_series_range(granularity, default_start)
        # The series helper applies the date range itself: created by created_at, resolved by completed_at.
        return build_created_vs_resolved_series(queryset, granularity, start_date, end_date)

    def project_distribution_chart(self) -> Dict[str, Any]:
        today = timezone.localdate()
        queryset = self.get_issue_queryset()
        if self.filters["chart_period_range"]:
            start_date, end_date = self.filters["chart_period_range"]
            queryset = queryset.filter(**date_range_filter("created_at__date", start_date, end_date))
        rows = (
            queryset.values("project_id", "project__name")
            .annotate(
                count=Count("id"),
                completed_work_items=Count("id", filter=Q(state__group="completed")),
                pending_work_items=Count("id", filter=Q(state__group__in=PENDING_STATE_GROUPS)),
                overdue_work_items=Count("id", filter=overdue_filter(today)),
            )
            .order_by("-count", "project__name")
        )
        data = [
            {
                "key": str(row["project_id"]),
                "name": row["project__name"],
                "count": row["count"],
                "completed_work_items": row["completed_work_items"],
                "pending_work_items": row["pending_work_items"],
                "overdue_work_items": row["overdue_work_items"],
            }
            for row in rows
        ]
        schema = {
            "completed_work_items": "completed_work_items",
            "pending_work_items": "pending_work_items",
            "overdue_work_items": "overdue_work_items",
        }
        return {"data": data, "schema": schema}

    def time_logged_chart(self) -> Dict[str, Any]:
        granularity = get_granularity(self.request.GET.get("granularity"))
        start_date, end_date = self.get_series_range(granularity, get_default_series_start(granularity))
        rows = (
            self.get_worklog_queryset()
            .filter(logged_at__gte=align_to_bucket(start_date, granularity), logged_at__lte=end_date)
            .annotate(bucket=get_trunc_function(granularity)("logged_at"))
            .values("bucket", "project_id", "project__name")
            .annotate(minutes=Sum("duration"))
            .order_by("bucket")
        )

        schema: Dict[str, str] = {}
        minutes_by_bucket: Dict[str, Dict[str, int]] = {}
        for row in rows:
            project_key = str(row["project_id"])
            schema[project_key] = row["project__name"]
            bucket_key = to_date(row["bucket"]).strftime("%Y-%m-%d")
            minutes_by_bucket.setdefault(bucket_key, {})[project_key] = row["minutes"]

        data = []
        for bucket_start in get_bucket_starts(start_date, end_date, granularity):
            date_str = bucket_start.strftime("%Y-%m-%d")
            bucket_minutes = minutes_by_bucket.get(date_str, {})
            datum: Dict[str, Any] = {
                "key": date_str,
                "name": date_str,
                "count": minutes_to_hours(sum(bucket_minutes.values())),
            }
            for project_key in schema:
                datum[project_key] = minutes_to_hours(bucket_minutes.get(project_key))
            data.append(datum)

        return {"data": data, "schema": schema}

    def allocated_vs_spent_chart(self) -> Dict[str, Any]:
        granularity = get_granularity(self.request.GET.get("granularity"))
        start_date, end_date = self.get_series_range(granularity, get_default_series_start(granularity))
        range_start = align_to_bucket(start_date, granularity)
        trunc = get_trunc_function(granularity)

        # Allocation is planned against the item's due date, falling back to its start, then creation.
        planned_on = Coalesce("target_date", "start_date", TruncDate("created_at"))
        allocated_rows = (
            self.get_issue_queryset()
            .filter(TIME_ESTIMATED)
            .annotate(planned_on=planned_on)
            .filter(planned_on__gte=range_start, planned_on__lte=end_date)
            .annotate(bucket=trunc("planned_on"))
            .values("bucket")
            .annotate(minutes=Sum(allocated_minutes()))
            .order_by()
        )
        spent_rows = (
            self.get_worklog_queryset()
            .filter(logged_at__gte=range_start, logged_at__lte=end_date)
            .annotate(bucket=trunc("logged_at"))
            .values("bucket")
            .annotate(minutes=Sum("duration"))
            .order_by()
        )
        allocated = {to_date(row["bucket"]).strftime("%Y-%m-%d"): row["minutes"] for row in allocated_rows}
        spent = {to_date(row["bucket"]).strftime("%Y-%m-%d"): row["minutes"] for row in spent_rows}

        data = []
        for bucket_start in get_bucket_starts(start_date, end_date, granularity):
            date_str = bucket_start.strftime("%Y-%m-%d")
            spent_hours = minutes_to_hours(spent.get(date_str))
            data.append(
                {
                    "key": date_str,
                    "name": date_str,
                    "count": spent_hours,
                    "allocated_hours": minutes_to_hours(allocated.get(date_str)),
                    "spent_hours": spent_hours,
                }
            )
        return {"data": data, "schema": {"allocated_hours": "allocated_hours", "spent_hours": "spent_hours"}}

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request: HttpRequest, slug: str) -> Response:
        self.initialize_workspace(slug, type="chart")
        type = request.GET.get("type", "projects")
        group_by = request.GET.get("group_by", None)
        x_axis = request.GET.get("x_axis", "PRIORITY")

        if type == "projects":
            return Response(self.project_chart(), status=status.HTTP_200_OK)

        elif type == "custom-work-items":
            queryset = (
                Issue.issue_objects.filter(**self.filters["base_filters"])
                .select_related("workspace", "state", "parent")
                .prefetch_related("assignees", "labels", "issue_module__module", "issue_cycle__cycle")
            )

            # Apply date range filter if available
            if self.filters["chart_period_range"]:
                start_date, end_date = self.filters["chart_period_range"]
                queryset = queryset.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

            return Response(
                build_analytics_chart(queryset, x_axis, group_by),
                status=status.HTTP_200_OK,
            )

        elif type == "work-items":
            return Response(
                self.work_item_completion_chart(),
                status=status.HTTP_200_OK,
            )

        elif type == "project-distribution":
            return Response(self.project_distribution_chart(), status=status.HTTP_200_OK)

        elif type == "time-logged":
            return Response(self.time_logged_chart(), status=status.HTTP_200_OK)

        elif type == "allocated-vs-spent":
            return Response(self.allocated_vs_spent_chart(), status=status.HTTP_200_OK)

        return Response({"message": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
