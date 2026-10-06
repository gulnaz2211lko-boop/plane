# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.response import Response
from rest_framework import status
from typing import Dict, Any
from django.db.models import QuerySet, Q, Count
from django.http import HttpRequest
from django.utils import timezone
from plane.app.views.base import BaseAPIView
from plane.app.permissions import ROLE, allow_permission
from plane.db.models import (
    Project,
    Issue,
    Cycle,
    Module,
    CycleIssue,
    ModuleIssue,
)
from django.db import models
from django.db.models import F, Case, When, Value
from django.db.models.functions import Cast, Concat
from plane.utils.build_chart import build_analytics_chart, build_created_vs_resolved_series
from plane.utils.date_utils import (
    get_analytics_filters,
    get_default_series_start,
    get_granularity,
)


class ProjectAdvanceAnalyticsBaseView(BaseAPIView):
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


class ProjectAdvanceAnalyticsEndpoint(ProjectAdvanceAnalyticsBaseView):
    def get_filtered_counts(self, queryset: QuerySet) -> Dict[str, int]:
        def get_filtered_count() -> int:
            if self.filters["analytics_date_range"]:
                return queryset.filter(
                    created_at__gte=self.filters["analytics_date_range"]["current"]["gte"],
                    created_at__lte=self.filters["analytics_date_range"]["current"]["lte"],
                ).count()
            return queryset.count()

        return {
            "count": get_filtered_count(),
        }

    def get_work_items_stats(self, project_id, cycle_id=None, module_id=None) -> Dict[str, Dict[str, int]]:
        """
        Returns work item stats for the workspace, or filtered by cycle_id or module_id if provided.
        """
        base_queryset = None
        if cycle_id is not None:
            cycle_issues = CycleIssue.objects.filter(**self.filters["base_filters"], cycle_id=cycle_id).values_list(
                "issue_id", flat=True
            )
            base_queryset = Issue.issue_objects.filter(id__in=cycle_issues)
        elif module_id is not None:
            module_issues = ModuleIssue.objects.filter(**self.filters["base_filters"], module_id=module_id).values_list(
                "issue_id", flat=True
            )
            base_queryset = Issue.issue_objects.filter(id__in=module_issues)
        else:
            base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"], project_id=project_id)

        return {
            "total_work_items": self.get_filtered_counts(base_queryset),
            "started_work_items": self.get_filtered_counts(base_queryset.filter(state__group="started")),
            "backlog_work_items": self.get_filtered_counts(base_queryset.filter(state__group="backlog")),
            "un_started_work_items": self.get_filtered_counts(base_queryset.filter(state__group="unstarted")),
            "completed_work_items": self.get_filtered_counts(base_queryset.filter(state__group="completed")),
        }

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request: HttpRequest, slug: str, project_id: str) -> Response:
        self.initialize_workspace(slug, type="analytics")

        # Optionally accept cycle_id or module_id as query params
        cycle_id = request.GET.get("cycle_id", None)
        module_id = request.GET.get("module_id", None)
        return Response(
            self.get_work_items_stats(cycle_id=cycle_id, module_id=module_id, project_id=project_id),
            status=status.HTTP_200_OK,
        )


class ProjectAdvanceAnalyticsStatsEndpoint(ProjectAdvanceAnalyticsBaseView):
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

    def get_work_items_stats(self, project_id, cycle_id=None, module_id=None) -> Dict[str, Dict[str, int]]:
        base_queryset = None
        if cycle_id is not None:
            cycle_issues = CycleIssue.objects.filter(**self.filters["base_filters"], cycle_id=cycle_id).values_list(
                "issue_id", flat=True
            )
            base_queryset = Issue.issue_objects.filter(id__in=cycle_issues)
        elif module_id is not None:
            module_issues = ModuleIssue.objects.filter(**self.filters["base_filters"], module_id=module_id).values_list(
                "issue_id", flat=True
            )
            base_queryset = Issue.issue_objects.filter(id__in=module_issues)
        else:
            base_queryset = Issue.issue_objects.filter(**self.filters["base_filters"], project_id=project_id)
        return (
            base_queryset.annotate(display_name=F("assignees__display_name"))
            .annotate(assignee_id=F("assignees__id"))
            .annotate(avatar=F("assignees__avatar"))
            .annotate(
                avatar_url=Case(
                    # If `avatar_asset` exists, use it to generate the asset URL
                    When(
                        assignees__avatar_asset__isnull=False,
                        then=Concat(
                            Value("/api/assets/v2/static/"),
                            Cast("assignees__avatar_asset", models.CharField()),
                            Value("/"),
                        ),
                    ),
                    # If `avatar_asset` is None, fall back to using `avatar` field directly
                    When(assignees__avatar_asset__isnull=True, then="assignees__avatar"),
                    default=Value(None),
                    output_field=models.CharField(),
                )
            )
            .values("display_name", "assignee_id", "avatar_url")
            .annotate(
                cancelled_work_items=Count("id", filter=Q(state__group="cancelled"), distinct=True),
                completed_work_items=Count("id", filter=Q(state__group="completed"), distinct=True),
                backlog_work_items=Count("id", filter=Q(state__group="backlog"), distinct=True),
                un_started_work_items=Count("id", filter=Q(state__group="unstarted"), distinct=True),
                started_work_items=Count("id", filter=Q(state__group="started"), distinct=True),
            )
            .order_by("display_name")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request: HttpRequest, slug: str, project_id: str) -> Response:
        self.initialize_workspace(slug, type="chart")
        type = request.GET.get("type", "work-items")

        if type == "work-items":
            # Optionally accept cycle_id or module_id as query params
            cycle_id = request.GET.get("cycle_id", None)
            module_id = request.GET.get("module_id", None)
            return Response(
                self.get_work_items_stats(project_id=project_id, cycle_id=cycle_id, module_id=module_id),
                status=status.HTTP_200_OK,
            )

        return Response({"message": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)


class ProjectAdvanceAnalyticsChartEndpoint(ProjectAdvanceAnalyticsBaseView):
    def work_item_completion_chart(self, project_id, cycle_id=None, module_id=None) -> Dict[str, Any]:
        # Get the base queryset
        queryset = (
            Issue.issue_objects.filter(**self.filters["base_filters"])
            .filter(project_id=project_id)
            .select_related("workspace", "state", "parent")
            .prefetch_related("assignees", "labels", "issue_module__module", "issue_cycle__cycle")
        )

        if cycle_id is not None:
            cycle = Cycle.objects.filter(id=cycle_id).first()
            if not cycle or not cycle.start_date or not cycle.end_date:
                return {"data": [], "schema": {}}
            # "Created" for a cycle means added to the cycle, so bucket the CycleIssue rows.
            cycle_issues = CycleIssue.objects.filter(
                **self.filters["base_filters"], cycle_id=cycle_id, issue__deleted_at__isnull=True
            )
            return build_created_vs_resolved_series(
                cycle_issues, "day", cycle.start_date.date(), cycle.end_date.date(), issue_prefix="issue__"
            )

        if module_id is not None:
            module = Module.objects.filter(id=module_id).first()
            if not module or not module.start_date or not module.target_date:
                return {"data": [], "schema": {}}
            module_issues = ModuleIssue.objects.filter(
                **self.filters["base_filters"], module_id=module_id, issue__deleted_at__isnull=True
            )
            return build_created_vs_resolved_series(
                module_issues, "day", module.start_date, module.target_date, issue_prefix="issue__"
            )

        project = Project.objects.filter(id=project_id).first()
        if not project or not project.created_at:
            return {"data": [], "schema": {}}
        granularity = get_granularity(self.request.GET.get("granularity"))
        if self.filters["chart_period_range"]:
            start_date, end_date = self.filters["chart_period_range"]
        else:
            start_date = (
                project.created_at.date().replace(day=1)
                if granularity == "month"
                else get_default_series_start(granularity)
            )
            end_date = timezone.localdate()
        return build_created_vs_resolved_series(queryset, granularity, start_date, end_date)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request: HttpRequest, slug: str, project_id: str) -> Response:
        self.initialize_workspace(slug, type="chart")
        type = request.GET.get("type", "projects")
        group_by = request.GET.get("group_by", None)
        x_axis = request.GET.get("x_axis", "PRIORITY")
        cycle_id = request.GET.get("cycle_id", None)
        module_id = request.GET.get("module_id", None)

        if type == "custom-work-items":
            queryset = (
                Issue.issue_objects.filter(**self.filters["base_filters"])
                .filter(project_id=project_id)
                .select_related("workspace", "state", "parent")
                .prefetch_related("assignees", "labels", "issue_module__module", "issue_cycle__cycle")
            )

            # Apply cycle/module filters if present
            if cycle_id is not None:
                cycle_issues = CycleIssue.objects.filter(**self.filters["base_filters"], cycle_id=cycle_id).values_list(
                    "issue_id", flat=True
                )
                queryset = queryset.filter(id__in=cycle_issues)

            elif module_id is not None:
                module_issues = ModuleIssue.objects.filter(
                    **self.filters["base_filters"], module_id=module_id
                ).values_list("issue_id", flat=True)
                queryset = queryset.filter(id__in=module_issues)

            # Apply date range filter if available
            if self.filters["chart_period_range"]:
                start_date, end_date = self.filters["chart_period_range"]
                queryset = queryset.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)

            return Response(
                build_analytics_chart(queryset, x_axis, group_by),
                status=status.HTTP_200_OK,
            )

        elif type == "work-items":
            # Optionally accept cycle_id or module_id as query params
            cycle_id = request.GET.get("cycle_id", None)
            module_id = request.GET.get("module_id", None)

            return Response(
                self.work_item_completion_chart(project_id=project_id, cycle_id=cycle_id, module_id=module_id),
                status=status.HTTP_200_OK,
            )

        return Response({"message": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
