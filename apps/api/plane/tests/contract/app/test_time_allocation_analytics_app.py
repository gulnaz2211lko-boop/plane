# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for resolved-by-completion-date charts, time estimates (allocated vs spent) and query budgets."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from plane.db.models import (
    Cycle,
    CycleIssue,
    Estimate,
    EstimatePoint,
    Issue,
    IssueAssignee,
    IssueWorklog,
    Teamspace,
    TeamspaceMember,
    TeamspaceProject,
    User,
    WorkspaceMember,
)
from plane.tests.contract.app.test_project_teamspace_analytics_app import create_issue, create_project

ANALYTICS_URL = "/api/workspaces/{slug}/advance-analytics/"
STATS_URL = "/api/workspaces/{slug}/advance-analytics-stats/"
CHARTS_URL = "/api/workspaces/{slug}/advance-analytics-charts/"


def by_key(series):
    return {item["key"]: item for item in series}


@pytest.fixture
def allocation(db, workspace, create_user):
    """
    Alpha uses a time estimate (2h / 4h points), Beta a points estimate. Alpha is shared by two teamspaces.
    Alpha: 2h item (assigned to user + teammate, due today) and 4h item (assigned to teammate, due in 10 days).
    Logged: 3h on Alpha by the user, 1h on Beta by the user.
    """
    today = timezone.now().date()
    teammate = User.objects.create(email="teammate@plane.so", username="teammate", display_name="teammate")
    WorkspaceMember.objects.create(workspace=workspace, member=teammate, role=15)

    alpha, alpha_states = create_project(workspace, create_user, "Alpha", "ALP")
    beta, beta_states = create_project(workspace, create_user, "Beta", "BET")

    time_estimate = Estimate.objects.create(name="Hours", type="time", project=alpha)
    two_hours = EstimatePoint.objects.create(estimate=time_estimate, key=1, value="120", project=alpha)
    four_hours = EstimatePoint.objects.create(estimate=time_estimate, key=2, value="240", project=alpha)
    points = Estimate.objects.create(name="Fib", type="points", project=beta)
    eight = EstimatePoint.objects.create(estimate=points, key=1, value="8", project=beta)

    small = create_issue(alpha, alpha_states, create_user, "started", estimate_point=two_hours, target_date=today)
    big = create_issue(
        alpha, alpha_states, create_user, "backlog", estimate_point=four_hours, target_date=today + timedelta(days=10)
    )
    beta_issue = create_issue(beta, beta_states, create_user, "started", estimate_point=eight)

    IssueAssignee.objects.create(issue=small, assignee=create_user, project=alpha)
    IssueAssignee.objects.create(issue=small, assignee=teammate, project=alpha)
    IssueAssignee.objects.create(issue=big, assignee=teammate, project=alpha)

    IssueWorklog.objects.create(issue=small, project=alpha, logged_by=create_user, duration=180, logged_at=today)
    IssueWorklog.objects.create(issue=beta_issue, project=beta, logged_by=create_user, duration=60, logged_at=today)

    platform = Teamspace.objects.create(name="Platform", workspace=workspace)
    product = Teamspace.objects.create(name="Product", workspace=workspace)
    TeamspaceProject.objects.create(teamspace=platform, project=alpha, workspace=workspace)
    TeamspaceProject.objects.create(teamspace=platform, project=beta, workspace=workspace)
    TeamspaceProject.objects.create(teamspace=product, project=alpha, workspace=workspace)
    TeamspaceMember.objects.create(teamspace=platform, member=create_user, workspace=workspace)
    TeamspaceMember.objects.create(teamspace=platform, member=teammate, workspace=workspace)
    return {
        "today": today,
        "teammate": teammate,
        "alpha": alpha,
        "beta": beta,
        "alpha_states": alpha_states,
        "platform": platform,
        "product": product,
    }


@pytest.mark.contract
@pytest.mark.django_db
class TestResolvedByCompletionDate:
    def test_old_item_completed_today_is_resolved_today(self, session_client, workspace, create_user):
        today = timezone.now().date()
        project, states = create_project(workspace, create_user, "Gamma", "GAM")
        old = create_issue(project, states, create_user, "completed")
        reopened = create_issue(project, states, create_user, "started")
        # Created 20 days ago, completed today; the reopened item has a stale completed_at but is not done.
        Issue.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=20))
        Issue.objects.filter(pk=reopened.pk).update(completed_at=timezone.now())

        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
        )
        assert response.status_code == status.HTTP_200_OK
        series = by_key(response.data["data"])
        created_day = (today - timedelta(days=20)).isoformat()
        assert series[created_day]["created_issues"] == 1
        assert series[created_day]["completed_issues"] == 0
        assert series[today.isoformat()]["created_issues"] == 1
        assert series[today.isoformat()]["completed_issues"] == 1

    def test_completion_before_window_not_counted(self, session_client, workspace, create_user):
        project, states = create_project(workspace, create_user, "Gamma", "GAM")
        done = create_issue(project, states, create_user, "completed")
        Issue.objects.filter(pk=done.pk).update(completed_at=timezone.now() - timedelta(days=60))

        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
        )
        assert sum(item["completed_issues"] for item in response.data["data"]) == 0

    def test_cycle_chart_buckets_resolved_by_completion(self, session_client, workspace, create_user):
        today = timezone.now().date()
        project, states = create_project(workspace, create_user, "Gamma", "GAM")
        cycle = Cycle.objects.create(
            name="Sprint",
            project=project,
            workspace=workspace,
            owned_by=create_user,
            start_date=timezone.now() - timedelta(days=6),
            end_date=timezone.now() + timedelta(days=7),
        )
        done = create_issue(project, states, create_user, "completed")
        cycle_issue = CycleIssue.objects.create(cycle=cycle, issue=done, project=project, workspace=workspace)
        CycleIssue.objects.filter(pk=cycle_issue.pk).update(created_at=timezone.now() - timedelta(days=5))

        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/advance-analytics-charts/",
            {"type": "work-items", "cycle_id": str(cycle.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        series = by_key(response.data["data"])
        assert series[(today - timedelta(days=5)).isoformat()]["created_issues"] == 1
        assert series[(today - timedelta(days=5)).isoformat()]["completed_issues"] == 0
        assert series[today.isoformat()]["completed_issues"] == 1


@pytest.mark.contract
@pytest.mark.django_db
class TestAllocatedVsSpent:
    def test_time_tracking_totals_include_allocation(self, session_client, workspace, allocation):
        response = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"})
        assert response.status_code == status.HTTP_200_OK
        # 2h + 4h allocated on Alpha; Beta's points estimate must not be read as minutes.
        assert response.data["total_estimated_time"] == {"count": 6.0}
        assert response.data["total_time_logged"] == {"count": 4.0}
        assert response.data["utilization_percentage"] == {"count": 66.7}

    def test_project_rows_have_allocation_and_utilization(self, session_client, workspace, allocation):
        response = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"})
        rows = {row["project__name"]: row for row in response.data}
        assert rows["Alpha"]["estimated_time"] == 6.0
        assert rows["Alpha"]["time_logged"] == 3.0
        assert rows["Alpha"]["utilization_percentage"] == 50.0
        assert rows["Beta"]["estimated_time"] == 0.0
        assert rows["Beta"]["utilization_percentage"] is None
        assert rows["Beta"]["estimate_points"] == 8.0

    def test_member_rows_merge_allocation_and_logs(self, session_client, workspace, create_user, allocation):
        response = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "time-tracking"})
        rows = {(row["project__name"], row["member_id"]): row for row in response.data}
        alpha, user_id, teammate_id = "Alpha", str(create_user.id), str(allocation["teammate"].id)
        assert rows[(alpha, user_id)]["time_logged"] == 3.0
        assert rows[(alpha, user_id)]["estimated_time"] == 2.0
        # The teammate has allocation but has not logged anything yet.
        assert rows[(alpha, teammate_id)]["time_logged"] == 0.0
        assert rows[(alpha, teammate_id)]["estimated_time"] == 6.0
        assert rows[(alpha, teammate_id)]["work_items_logged"] == 0
        assert rows[(alpha, teammate_id)]["display_name"] == "teammate"
        assert rows[("Beta", user_id)]["estimated_time"] == 0.0
        assert [row["time_logged"] for row in response.data] == sorted(
            (row["time_logged"] for row in response.data), reverse=True
        )

    def test_teamspace_rows(self, session_client, workspace, allocation):
        response = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "teamspaces"})
        assert response.status_code == status.HTTP_200_OK
        assert [row["name"] for row in response.data] == ["Platform", "Product"]
        platform, product = response.data
        assert platform == {
            "teamspace_id": str(allocation["platform"].id),
            "name": "Platform",
            "total_projects": 2,
            "total_members": 2,
            "total_work_items": 3,
            "completed_work_items": 0,
            "pending_work_items": 3,
            "estimated_time": 6.0,
            "time_logged": 4.0,
            "utilization_percentage": 66.7,
        }
        # A project shared by two teamspaces counts fully in each.
        assert product["total_projects"] == 1
        assert product["estimated_time"] == 6.0
        assert product["time_logged"] == 3.0
        assert product["utilization_percentage"] == 50.0

    def test_teamspace_rows_respect_filters(self, session_client, workspace, allocation):
        response = session_client.get(
            STATS_URL.format(slug=workspace.slug),
            {"type": "teamspaces", "teamspace_ids": str(allocation["platform"].id)},
        )
        assert [row["name"] for row in response.data] == ["Platform"]

        response = session_client.get(
            STATS_URL.format(slug=workspace.slug), {"type": "teamspaces", "project_ids": str(allocation["beta"].id)}
        )
        rows = {row["name"]: row for row in response.data}
        assert rows["Platform"]["total_projects"] == 1
        assert rows["Platform"]["time_logged"] == 1.0
        assert rows["Product"]["total_projects"] == 0

        response = session_client.get(
            STATS_URL.format(slug=workspace.slug), {"type": "teamspaces", "teamspace_ids": "not-a-uuid"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_allocated_vs_spent_daily(self, session_client, workspace, allocation):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "allocated-vs-spent", "granularity": "day"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["schema"] == {"allocated_hours": "allocated_hours", "spent_hours": "spent_hours"}
        series = response.data["data"]
        assert len(series) == 30
        # The 4h item is due in 10 days, outside the default 30-day look-back.
        assert series[-1] == {
            "key": allocation["today"].isoformat(),
            "name": allocation["today"].isoformat(),
            "count": 4.0,
            "allocated_hours": 2.0,
            "spent_hours": 4.0,
        }
        assert sum(item["allocated_hours"] for item in series) == 2.0

    def test_allocated_vs_spent_teamspace_filter(self, session_client, workspace, allocation):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug),
            {"type": "allocated-vs-spent", "granularity": "week", "teamspace_ids": str(allocation["product"].id)},
        )
        series = response.data["data"]
        assert len(series) == 12
        assert sum(item["spent_hours"] for item in series) == 3.0


@pytest.mark.contract
@pytest.mark.django_db
class TestTimeEstimateValidation:
    def url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/estimates/"

    def test_time_estimate_created_with_minutes(self, session_client, workspace, create_user):
        project, _ = create_project(workspace, create_user, "Gamma", "GAM")
        response = session_client.post(
            self.url(workspace, project),
            {"estimate": {"name": "Hours", "type": "time"}, "estimate_points": [{"key": 1, "value": "60"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "time"

    @pytest.mark.parametrize("value", ["abc", "0", "-30", "1.5"])
    def test_time_estimate_rejects_non_minutes(self, session_client, workspace, create_user, value):
        project, _ = create_project(workspace, create_user, "Gamma", "GAM")
        response = session_client.post(
            self.url(workspace, project),
            {"estimate": {"name": "Hours", "type": "time"}, "estimate_points": [{"key": 1, "value": value}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Estimate.objects.filter(project=project).exists()

    def test_unknown_estimate_type_rejected(self, session_client, workspace, create_user):
        project, _ = create_project(workspace, create_user, "Gamma", "GAM")
        response = session_client.post(
            self.url(workspace, project),
            {"estimate": {"name": "X", "type": "bananas"}, "estimate_points": [{"key": 1, "value": "1"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_point_estimates_unchanged(self, session_client, workspace, create_user):
        project, _ = create_project(workspace, create_user, "Gamma", "GAM")
        response = session_client.post(
            self.url(workspace, project),
            {"estimate": {"name": "Fib", "type": "points"}, "estimate_points": [{"key": 1, "value": "1.5"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
@pytest.mark.django_db
class TestQueryBudget:
    """Aggregations must not issue queries per project / teamspace / member."""

    def seed(self, workspace, user, count, offset):
        teamspace = Teamspace.objects.create(name=f"T{offset}", workspace=workspace)
        TeamspaceMember.objects.create(teamspace=teamspace, member=user, workspace=workspace)
        for index in range(count):
            project, states = create_project(workspace, user, f"P{offset}-{index}", f"P{offset}{index}"[:12])
            issue = create_issue(project, states, user, "started")
            IssueAssignee.objects.create(issue=issue, assignee=user, project=project)
            IssueWorklog.objects.create(issue=issue, project=project, logged_by=user, duration=30)
            TeamspaceProject.objects.create(teamspace=teamspace, project=project, workspace=workspace)

    def count_queries(self, client, url, params):
        with CaptureQueriesContext(connection) as context:
            response = client.get(url, params)
        assert response.status_code == status.HTTP_200_OK
        return len(context.captured_queries)

    @pytest.mark.parametrize(
        "url,params",
        [
            (STATS_URL, {"type": "projects"}),
            (STATS_URL, {"type": "time-tracking"}),
            (STATS_URL, {"type": "teamspaces"}),
            (ANALYTICS_URL, {"tab": "projects"}),
            (ANALYTICS_URL, {"tab": "progress"}),
            (CHARTS_URL, {"type": "allocated-vs-spent", "granularity": "week"}),
            (CHARTS_URL, {"type": "time-logged", "granularity": "week"}),
        ],
    )
    def test_query_count_independent_of_size(self, session_client, workspace, create_user, url, params):
        self.seed(workspace, create_user, 2, 0)
        small = self.count_queries(session_client, url.format(slug=workspace.slug), params)
        self.seed(workspace, create_user, 8, 1)
        large = self.count_queries(session_client, url.format(slug=workspace.slug), params)
        assert large == small
