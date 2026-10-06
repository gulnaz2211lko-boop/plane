# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for project-level / teamspace-filtered analytics and time tracking analytics."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from plane.db.models import (
    Cycle,
    Estimate,
    EstimatePoint,
    Issue,
    IssueActivity,
    IssueWorklog,
    Module,
    Project,
    ProjectMember,
    State,
    Teamspace,
    TeamspaceProject,
)

ANALYTICS_URL = "/api/workspaces/{slug}/advance-analytics/"
STATS_URL = "/api/workspaces/{slug}/advance-analytics-stats/"
CHARTS_URL = "/api/workspaces/{slug}/advance-analytics-charts/"


def create_project(workspace, user, name, identifier, member=True):
    project = Project.objects.create(name=name, identifier=identifier, workspace=workspace, created_by=user)
    if member:
        ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=20)
    states = {
        group: State.objects.create(name=group.title(), project=project, group=group, default=group == "backlog")
        for group in ["backlog", "started", "completed", "cancelled"]
    }
    return project, states


def create_issue(project, states, user, group, **kwargs):
    return Issue.objects.create(
        name=f"{project.identifier}-{group}",
        workspace=project.workspace,
        project=project,
        state=states[group],
        created_by=user,
        **kwargs,
    )


@pytest.fixture
def data(db, workspace, create_user):
    today = timezone.now().date()
    alpha, alpha_states = create_project(workspace, create_user, "Alpha", "ALP")
    beta, beta_states = create_project(workspace, create_user, "Beta", "BET")
    # The user is not a member of this project, so it must never show up.
    hidden, hidden_states = create_project(workspace, create_user, "Hidden", "HID", member=False)

    estimate = Estimate.objects.create(name="Fib", type="points", project=alpha)
    three = EstimatePoint.objects.create(estimate=estimate, key=1, value="3", project=alpha)
    five = EstimatePoint.objects.create(estimate=estimate, key=2, value="5", project=alpha)

    alpha_done = create_issue(alpha, alpha_states, create_user, "completed", estimate_point=three)
    create_issue(alpha, alpha_states, create_user, "started", estimate_point=five)
    create_issue(alpha, alpha_states, create_user, "backlog", target_date=today - timedelta(days=2))
    create_issue(alpha, alpha_states, create_user, "cancelled")
    beta_issue = create_issue(beta, beta_states, create_user, "started")
    create_issue(hidden, hidden_states, create_user, "started")

    Cycle.objects.create(name="C1", project=alpha, workspace=workspace, owned_by=create_user)
    Module.objects.create(name="M1", project=alpha, workspace=workspace)

    IssueWorklog.objects.create(issue=alpha_done, project=alpha, logged_by=create_user, duration=90, logged_at=today)
    IssueWorklog.objects.create(
        issue=alpha_done, project=alpha, logged_by=create_user, duration=30, logged_at=today - timedelta(days=7)
    )
    IssueWorklog.objects.create(issue=beta_issue, project=beta, logged_by=create_user, duration=60, logged_at=today)
    IssueActivity.objects.create(
        issue=alpha_done, project=alpha, workspace=workspace, actor=create_user, verb="created"
    )

    platform = Teamspace.objects.create(name="Platform", workspace=workspace)
    TeamspaceProject.objects.create(teamspace=platform, project=alpha, workspace=workspace)
    empty = Teamspace.objects.create(name="Empty", workspace=workspace)
    return {
        "today": today,
        "alpha": alpha,
        "beta": beta,
        "hidden": hidden,
        "platform": platform,
        "empty": empty,
    }


def counts(response_data):
    return {key: value["count"] for key, value in response_data.items()}


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectsTab:
    def test_projects_totals(self, session_client, workspace, data):
        response = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects"})
        assert response.status_code == status.HTTP_200_OK
        assert counts(response.data) == {
            "total_projects": 2,
            "total_work_items": 5,
            "completed_work_items": 1,
            "overdue_work_items": 1,
            "total_members": 1,
            "total_time_logged": 3.0,
        }

    def test_teamspace_filter_narrows_projects(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": str(data["platform"].id)}
        )
        assert counts(response.data)["total_projects"] == 1
        assert counts(response.data)["total_work_items"] == 4
        assert counts(response.data)["total_time_logged"] == 2.0

    def test_teamspace_without_projects_matches_nothing(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": str(data["empty"].id)}
        )
        assert counts(response.data)["total_projects"] == 0
        assert counts(response.data)["total_work_items"] == 0

    def test_teamspace_and_project_filters_intersect(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug),
            {"tab": "work-items", "teamspace_ids": str(data["platform"].id), "project_ids": str(data["beta"].id)},
        )
        assert counts(response.data)["total_work_items"] == 0

    def test_existing_tabs_honor_teamspace_filter(self, session_client, workspace, data):
        params = {"teamspace_ids": str(data["platform"].id)}
        work_items = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "work-items", **params})
        overview = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "overview", **params})
        assert counts(work_items.data)["total_work_items"] == 4
        assert counts(overview.data)["total_projects"] == 1
        assert counts(overview.data)["total_users"] == 1

    def test_invalid_teamspace_id_matches_nothing(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": "not-a-uuid"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert counts(response.data)["total_projects"] == 0


@pytest.mark.contract
@pytest.mark.django_db
class TestTimeTrackingAndProgressTabs:
    def test_time_tracking_totals(self, session_client, workspace, data):
        response = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"})
        assert response.status_code == status.HTTP_200_OK
        assert counts(response.data) == {
            "total_time_logged": 3.0,
            "time_logged_this_week": 2.5,
            "time_logged_last_week": 0.5,
            "total_estimated_time": 0.0,
            "contributors": 1,
            "utilization_percentage": 0,
        }

    def test_progress_week(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "week"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["created_work_items"] == {"count": 5, "previous_count": 0}
        assert response.data["completed_work_items"] == {"count": 1, "previous_count": 0}
        assert response.data["time_logged"] == {"count": 2.5, "previous_count": 0.5}
        assert response.data["active_contributors"] == {"count": 1, "previous_count": 0}

    def test_progress_day(self, session_client, workspace, data):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "day"}
        )
        assert response.data["time_logged"] == {"count": 2.5, "previous_count": 0}

    def test_invalid_tab(self, session_client, workspace, data):
        response = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "nope"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestStats:
    def test_projects_stats_rows(self, session_client, workspace, data):
        response = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"})
        assert response.status_code == status.HTTP_200_OK
        assert [row["project__name"] for row in response.data] == ["Alpha", "Beta"]
        alpha = response.data[0]
        assert alpha == {
            "project_id": str(data["alpha"].id),
            "project__name": "Alpha",
            "total_work_items": 4,
            "completed_work_items": 1,
            "pending_work_items": 2,
            "cancelled_work_items": 1,
            "overdue_work_items": 1,
            "completion_percentage": 33.3,
            "total_members": 1,
            "total_cycles": 1,
            "total_modules": 1,
            "estimate_points": 8.0,
            "time_logged": 2.0,
            "estimated_time": 0.0,
            "utilization_percentage": None,
            "teamspace_ids": [str(data["platform"].id)],
        }
        beta = response.data[1]
        assert beta["estimate_points"] is None
        assert beta["teamspace_ids"] == []
        assert beta["time_logged"] == 1.0

    def test_time_tracking_stats_rows(self, session_client, workspace, create_user, data):
        response = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "time-tracking"})
        assert response.status_code == status.HTTP_200_OK
        assert [(row["project__name"], row["time_logged"], row["work_items_logged"]) for row in response.data] == [
            ("Alpha", 2.0, 1),
            ("Beta", 1.0, 1),
        ]
        assert response.data[0]["member_id"] == str(create_user.id)
        assert set(response.data[0]) == {
            "project_id",
            "project__name",
            "member_id",
            "display_name",
            "avatar_url",
            "time_logged",
            "estimated_time",
            "work_items_logged",
        }

    def test_projects_stats_teamspace_filter(self, session_client, workspace, data):
        response = session_client.get(
            STATS_URL.format(slug=workspace.slug), {"type": "projects", "teamspace_ids": str(data["platform"].id)}
        )
        assert [row["project__name"] for row in response.data] == ["Alpha"]


@pytest.mark.contract
@pytest.mark.django_db
class TestCharts:
    def test_work_items_daily_series(self, session_client, workspace, data):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
        )
        assert response.status_code == status.HTTP_200_OK
        series = response.data["data"]
        assert len(series) == 30
        assert series[-1]["key"] == data["today"].strftime("%Y-%m-%d")
        assert series[-1]["created_issues"] == 5
        assert series[-1]["completed_issues"] == 1
        assert sum(item["created_issues"] for item in series[:-1]) == 0

    def test_work_items_weekly_series_starts_on_mondays(self, session_client, workspace, data):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "week"}
        )
        series = response.data["data"]
        assert len(series) == 12
        today = data["today"]
        assert series[-1]["key"] == (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        assert series[-1]["created_issues"] == 5

    def test_work_items_monthly_default_unchanged(self, session_client, workspace, data):
        response = session_client.get(CHARTS_URL.format(slug=workspace.slug), {"type": "work-items"})
        series = response.data["data"]
        assert series[-1]["key"] == data["today"].replace(day=1).strftime("%Y-%m-%d")
        assert series[-1]["created_issues"] == 5
        assert response.data["schema"] == {"completed_issues": "completed_issues", "created_issues": "created_issues"}

    def test_project_distribution(self, session_client, workspace, data):
        response = session_client.get(CHARTS_URL.format(slug=workspace.slug), {"type": "project-distribution"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"][0] == {
            "key": str(data["alpha"].id),
            "name": "Alpha",
            "count": 4,
            "completed_work_items": 1,
            "pending_work_items": 2,
            "overdue_work_items": 1,
        }
        assert set(response.data["schema"]) == {"completed_work_items", "pending_work_items", "overdue_work_items"}

    def test_time_logged_daily(self, session_client, workspace, data):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "day"}
        )
        assert response.status_code == status.HTTP_200_OK
        alpha_key, beta_key = str(data["alpha"].id), str(data["beta"].id)
        assert response.data["schema"] == {alpha_key: "Alpha", beta_key: "Beta"}
        series = response.data["data"]
        assert len(series) == 30
        assert series[-1] == {
            "key": data["today"].strftime("%Y-%m-%d"),
            "name": data["today"].strftime("%Y-%m-%d"),
            "count": 2.5,
            alpha_key: 1.5,
            beta_key: 1.0,
        }
        week_ago = next(item for item in series if item["key"] == (data["today"] - timedelta(days=7)).isoformat())
        assert week_ago == {**week_ago, "count": 0.5, alpha_key: 0.5, beta_key: 0.0}

    def test_time_logged_teamspace_filter(self, session_client, workspace, data):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug),
            {"type": "time-logged", "granularity": "week", "teamspace_ids": str(data["platform"].id)},
        )
        assert list(response.data["schema"]) == [str(data["alpha"].id)]
        assert len(response.data["data"]) == 12

    def test_custom_chart_projects_axis(self, session_client, workspace, data):
        response = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "custom-work-items", "x_axis": "PROJECTS"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert {item["name"]: item["count"] for item in response.data["data"]} == {"Alpha": 4, "Beta": 1}

    def test_project_scoped_chart_honors_granularity(self, session_client, workspace, data):
        response = session_client.get(
            f"/api/workspaces/{workspace.slug}/projects/{data['alpha'].id}/advance-analytics-charts/",
            {"type": "work-items", "granularity": "week"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 12
        assert response.data["data"][-1]["created_issues"] == 4
