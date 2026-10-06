# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Edge cases for project aggregations, teamspace filters and time tracking metrics over time."""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    Estimate,
    EstimatePoint,
    Issue,
    IssueWorklog,
    Project,
    ProjectMember,
    Teamspace,
    TeamspaceMember,
    TeamspaceProject,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.tests.contract.app.test_project_teamspace_analytics_app import create_issue, create_project

ANALYTICS_URL = "/api/workspaces/{slug}/advance-analytics/"
STATS_URL = "/api/workspaces/{slug}/advance-analytics-stats/"
CHARTS_URL = "/api/workspaces/{slug}/advance-analytics-charts/"
WORKLOGS_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/worklogs/"


def counts(response_data):
    return {key: value["count"] for key, value in response_data.items()}


def by_key(series):
    return {item["key"]: item for item in series}


def ids(*objects):
    return ",".join(str(obj.id) for obj in objects)


def day_key(value):
    return value.strftime("%Y-%m-%d")


def utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


@pytest.fixture(autouse=True)
def reset_timezone():
    # Views activate the requesting user's timezone for the thread; don't leak it into other tests.
    yield
    timezone.deactivate()


@pytest.fixture
def world(db, workspace, create_user):
    """Alpha (3 work items) and Beta (1) are visible; Hidden (1) is a project the user is not a member of."""
    alpha, alpha_states = create_project(workspace, create_user, "Alpha", "ALP")
    beta, beta_states = create_project(workspace, create_user, "Beta", "BET")
    hidden, hidden_states = create_project(workspace, create_user, "Hidden", "HID", member=False)
    alpha_issues = [
        create_issue(alpha, alpha_states, create_user, group) for group in ("started", "backlog", "started")
    ]
    beta_issue = create_issue(beta, beta_states, create_user, "started")
    hidden_issue = create_issue(hidden, hidden_states, create_user, "started")
    return {
        "today": timezone.now().date(),
        "alpha": alpha,
        "alpha_states": alpha_states,
        "alpha_issues": alpha_issues,
        "beta": beta,
        "beta_states": beta_states,
        "beta_issue": beta_issue,
        "hidden": hidden,
        "hidden_issue": hidden_issue,
    }


def link(teamspace, *projects):
    for project in projects:
        TeamspaceProject.objects.create(teamspace=teamspace, project=project, workspace=teamspace.workspace)


def log_time(issue, user, minutes, logged_at):
    return IssueWorklog.objects.create(
        issue=issue, project=issue.project, logged_by=user, duration=minutes, logged_at=logged_at
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestVisibilityAndFilters:
    def test_workspace_without_projects_returns_zeroes(self, session_client, workspace):
        slug = workspace.slug
        for tab in ("projects", "time-tracking", "progress"):
            response = session_client.get(ANALYTICS_URL.format(slug=slug), {"tab": tab})
            assert response.status_code == status.HTTP_200_OK
            assert all(not value["count"] for value in response.data.values()), tab
        for stats_type in ("projects", "time-tracking", "teamspaces"):
            response = session_client.get(STATS_URL.format(slug=slug), {"type": stats_type})
            assert response.status_code == status.HTTP_200_OK
            assert response.data == []
        for chart_type in ("work-items", "time-logged", "allocated-vs-spent"):
            response = session_client.get(CHARTS_URL.format(slug=slug), {"type": chart_type, "granularity": "day"})
            assert response.status_code == status.HTTP_200_OK
            assert len(response.data["data"]) == 30
            assert all(item["count"] == 0 for item in response.data["data"])
        response = session_client.get(CHARTS_URL.format(slug=slug), {"type": "project-distribution"})
        assert response.data["data"] == []

    def test_archived_project_is_excluded(self, session_client, workspace, world):
        Project.objects.filter(id=world["beta"].id).update(archived_at=timezone.now())
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects"}).data)
        rows = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        assert totals["total_projects"] == 1
        assert totals["total_work_items"] == 3
        assert [row["project__name"] for row in rows] == ["Alpha"]

    def test_project_filter_cannot_reveal_a_project_the_user_is_not_in(self, session_client, workspace, world):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "project_ids": ids(world["hidden"])}
        )
        assert counts(response.data)["total_projects"] == 0
        assert counts(response.data)["total_work_items"] == 0

    def test_teamspace_filter_cannot_reveal_a_project_the_user_is_not_in(
        self, session_client, workspace, create_user, world
    ):
        secret = Teamspace.objects.create(name="Secret", workspace=workspace)
        link(secret, world["hidden"])
        log_time(world["hidden_issue"], create_user, 60, world["today"])
        params = {"teamspace_ids": ids(secret)}
        totals = counts(
            session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", **params}).data
        )
        teamspaces = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "teamspaces", **params}).data
        assert totals["total_projects"] == 0
        assert totals["total_time_logged"] == 0
        assert teamspaces == [
            {
                "teamspace_id": str(secret.id),
                "name": "Secret",
                "total_projects": 0,
                "total_members": 0,
                "total_work_items": 0,
                "completed_work_items": 0,
                "pending_work_items": 0,
                "estimated_time": 0,
                "time_logged": 0,
                "utilization_percentage": None,
            }
        ]

    def test_deleted_teamspace_matches_nothing_and_is_not_listed(self, session_client, workspace, world):
        gone = Teamspace.objects.create(name="Gone", workspace=workspace)
        link(gone, world["alpha"])
        Teamspace.objects.filter(id=gone.id).update(deleted_at=timezone.now())
        totals = counts(
            session_client.get(
                ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": ids(gone)}
            ).data
        )
        teamspaces = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "teamspaces"}).data
        rows = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        assert totals["total_projects"] == 0
        assert teamspaces == []
        # The project row no longer advertises the deleted teamspace.
        assert all(row["teamspace_ids"] == [] for row in rows)

    def test_teamspace_from_another_workspace_matches_nothing(self, session_client, workspace, create_user, world):
        other = Workspace.objects.create(name="Other", slug="other-workspace", owner=create_user)
        foreign = Teamspace.objects.create(name="Foreign", workspace=other)
        # Even if it somehow links a project of this workspace, it must not act as a filter here.
        link(foreign, world["alpha"])
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": ids(foreign)}
        )
        assert counts(response.data)["total_projects"] == 0

    def test_project_shared_by_selected_teamspaces_is_counted_once(self, session_client, workspace, world):
        platform = Teamspace.objects.create(name="Platform", workspace=workspace)
        product = Teamspace.objects.create(name="Product", workspace=workspace)
        link(platform, world["alpha"], world["beta"])
        link(product, world["alpha"])
        params = {"teamspace_ids": ids(platform, product)}
        totals = counts(
            session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", **params}).data
        )
        teamspaces = {
            row["name"]: row
            for row in session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "teamspaces", **params}).data
        }
        distribution = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "project-distribution", **params}
        ).data["data"]
        assert totals["total_projects"] == 2
        assert totals["total_work_items"] == 4
        assert {item["name"]: item["count"] for item in distribution} == {"Alpha": 3, "Beta": 1}
        # Each teamspace row still reports the shared project in full.
        assert teamspaces["Platform"]["total_work_items"] == 4
        assert teamspaces["Product"]["total_work_items"] == 3

    def test_blank_teamspace_filter_is_ignored(self, session_client, workspace, world):
        response = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects", "teamspace_ids": ""}
        )
        assert counts(response.data)["total_projects"] == 2

    def test_bots_are_not_counted_as_members(self, session_client, workspace, world):
        bot = User.objects.create(email="bot@plane.so", username="bot", is_bot=True)
        ProjectMember.objects.create(project=world["alpha"], member=bot, workspace=workspace, role=15)
        platform = Teamspace.objects.create(name="Platform", workspace=workspace)
        link(platform, world["alpha"])
        TeamspaceMember.objects.create(teamspace=platform, member=bot, workspace=workspace)
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects"}).data)
        rows = {
            row["project__name"]: row
            for row in session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        }
        teamspaces = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "teamspaces"}).data
        assert totals["total_members"] == 1
        assert rows["Alpha"]["total_members"] == 1
        assert teamspaces[0]["total_members"] == 0

    def test_member_of_several_projects_is_counted_once(self, session_client, workspace, world):
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "projects"}).data)
        assert totals["total_members"] == 1

    @pytest.mark.parametrize(
        "url,params",
        [
            (ANALYTICS_URL, {"tab": "projects"}),
            (STATS_URL, {"type": "teamspaces"}),
            (CHARTS_URL, {"type": "allocated-vs-spent"}),
        ],
    )
    def test_workspace_guest_is_forbidden(self, workspace, world, url, params):
        guest = User.objects.create(email="guest@plane.so", username="guest")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=5)
        client = APIClient()
        client.force_authenticate(user=guest)
        assert client.get(url.format(slug=workspace.slug), params).status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_stats_and_chart_types(self, session_client, workspace, world):
        stats = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "nope"})
        chart = session_client.get(CHARTS_URL.format(slug=workspace.slug), {"type": "nope"})
        assert stats.status_code == status.HTTP_400_BAD_REQUEST
        assert chart.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
class TestTimeTrackingEdgeCases:
    def time_estimate(self, project, *values):
        estimate = Estimate.objects.create(name="Hours", type="time", project=project)
        return [
            EstimatePoint.objects.create(estimate=estimate, key=index, value=value, project=project)
            for index, value in enumerate(values, start=1)
        ]

    def test_time_logged_on_a_deleted_work_item_is_excluded(self, session_client, workspace, create_user, world):
        kept, removed = world["alpha_issues"][:2]
        log_time(kept, create_user, 60, world["today"])
        log_time(removed, create_user, 120, world["today"])
        Issue.objects.filter(id=removed.id).update(deleted_at=timezone.now())
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data)
        members = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "time-tracking"}).data
        series = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "day"}
        ).data["data"]
        assert totals["total_time_logged"] == 1
        assert [(row["time_logged"], row["work_items_logged"]) for row in members] == [(1, 1)]
        assert series[-1]["count"] == 1

    def test_points_estimates_are_not_treated_as_allocated_time(self, session_client, workspace, create_user, world):
        points = Estimate.objects.create(name="Fib", type="points", project=world["alpha"])
        eight = EstimatePoint.objects.create(estimate=points, key=1, value="8", project=world["alpha"])
        Issue.objects.filter(id=world["alpha_issues"][0].id).update(estimate_point=eight)
        log_time(world["alpha_issues"][0], create_user, 60, world["today"])
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data)
        rows = {
            row["project__name"]: row
            for row in session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        }
        assert totals["total_estimated_time"] == 0
        assert totals["utilization_percentage"] == 0
        assert rows["Alpha"]["estimate_points"] == 8
        assert rows["Alpha"]["estimated_time"] == 0
        # Nothing allocated: utilisation is undefined, not 0% or a division error.
        assert rows["Alpha"]["utilization_percentage"] is None

    def test_non_numeric_time_estimate_value_is_ignored(self, session_client, workspace, world):
        # Values are validated on write, but legacy / imported rows must not break the aggregates.
        broken, valid = self.time_estimate(world["alpha"], "soon", " 90 ")
        Issue.objects.filter(id=world["alpha_issues"][0].id).update(estimate_point=broken)
        Issue.objects.filter(id=world["alpha_issues"][1].id).update(estimate_point=valid)
        response = session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"})
        assert response.status_code == status.HTTP_200_OK
        assert counts(response.data)["total_estimated_time"] == 1.5

    def test_utilization_can_exceed_one_hundred_percent(self, session_client, workspace, create_user, world):
        (one_hour,) = self.time_estimate(world["alpha"], "60")
        Issue.objects.filter(id=world["alpha_issues"][0].id).update(estimate_point=one_hour)
        log_time(world["alpha_issues"][0], create_user, 150, world["today"])
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data)
        assert totals["utilization_percentage"] == 250.0

    def test_allocation_date_falls_back_from_due_to_start_to_created(self, session_client, workspace, world):
        today = world["today"]
        (one_hour,) = self.time_estimate(world["alpha"], "60")
        due, started, undated = world["alpha_issues"]
        Issue.objects.filter(id=due.id).update(
            estimate_point=one_hour, target_date=today - timedelta(days=3), start_date=today - timedelta(days=9)
        )
        Issue.objects.filter(id=started.id).update(estimate_point=one_hour, start_date=today - timedelta(days=5))
        Issue.objects.filter(id=undated.id).update(estimate_point=one_hour)
        series = by_key(
            session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "allocated-vs-spent", "granularity": "day"}
            ).data["data"]
        )
        assert series[day_key(today - timedelta(days=3))]["allocated_hours"] == 1
        assert series[day_key(today - timedelta(days=5))]["allocated_hours"] == 1
        assert series[day_key(today)]["allocated_hours"] == 1
        assert series[day_key(today - timedelta(days=9))]["allocated_hours"] == 0
        assert sum(item["allocated_hours"] for item in series.values()) == 3

    def test_allocation_due_after_today_is_outside_the_default_window(self, session_client, workspace, world):
        (one_hour,) = self.time_estimate(world["alpha"], "60")
        Issue.objects.filter(id=world["alpha_issues"][0].id).update(
            estimate_point=one_hour, target_date=world["today"] + timedelta(days=1)
        )
        series = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "allocated-vs-spent", "granularity": "day"}
        ).data["data"]
        assert sum(item["allocated_hours"] for item in series) == 0

    def test_unassigned_allocation_has_no_member_row(self, session_client, workspace, world):
        (one_hour,) = self.time_estimate(world["alpha"], "60")
        Issue.objects.filter(id=world["alpha_issues"][0].id).update(estimate_point=one_hour)
        members = session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "time-tracking"}).data
        projects = {
            row["project__name"]: row
            for row in session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        }
        assert members == []
        assert projects["Alpha"]["estimated_time"] == 1

    def test_unknown_granularity_falls_back_to_the_default(self, session_client, workspace, create_user, world):
        log_time(world["alpha_issues"][0], create_user, 60, world["today"])
        series = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "year"}
        ).data["data"]
        progress = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "year"}
        ).data
        weekly = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "week"}
        ).data
        assert len(series) == 12
        assert all(item["key"].endswith("-01") for item in series)
        assert progress == weekly

    def test_reopened_work_item_is_no_longer_resolved(self, session_client, workspace, world):
        issue = world["alpha_issues"][0]
        issue.state = world["alpha_states"]["completed"]
        issue.save()

        def resolved():
            series = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
            ).data["data"]
            return sum(item["completed_issues"] for item in series)

        assert resolved() == 1
        issue.state = world["alpha_states"]["started"]
        issue.save()
        assert resolved() == 0

    def test_cancelled_work_items_are_not_resolved_and_not_in_completion_rate(self, session_client, workspace, world):
        done, cancelled, _ = world["alpha_issues"]
        done.state = world["alpha_states"]["completed"]
        done.save()
        cancelled.state = world["alpha_states"]["cancelled"]
        cancelled.save()
        rows = {
            row["project__name"]: row
            for row in session_client.get(STATS_URL.format(slug=workspace.slug), {"type": "projects"}).data
        }
        progress = session_client.get(
            ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "day"}
        ).data
        # 1 completed out of 2 that were not cancelled.
        assert rows["Alpha"]["completion_percentage"] == 50.0
        assert rows["Alpha"]["cancelled_work_items"] == 1
        # A project with no work items left to complete reports 0%, not a division error.
        assert rows["Beta"]["completion_percentage"] == 0.0
        assert progress["completed_work_items"]["count"] == 1


@pytest.mark.contract
@pytest.mark.django_db
class TestTimezonesAndPeriodBoundaries:
    def test_buckets_follow_the_users_timezone(self, session_client, workspace, create_user):
        project, states = create_project(workspace, create_user, "Alpha", "ALP")
        create_user.user_timezone = "Asia/Tokyo"
        create_user.save()
        # 20:00 UTC on the 10th is already 05:00 on the 11th in Tokyo.
        with freeze_time("2030-03-10 20:00:00"):
            issue = create_issue(project, states, create_user, "completed")
            log_time(issue, create_user, 60, timezone.localdate(timezone=None) + timedelta(days=1))
            series = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
            ).data["data"]
            progress = session_client.get(
                ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "day"}
            ).data
            logged = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "day"}
            ).data["data"]
        assert len(series) == 30
        assert series[-1]["key"] == "2030-03-11"
        assert series[-1]["created_issues"] == 1
        assert series[-1]["completed_issues"] == 1
        assert progress["created_work_items"] == {"count": 1, "previous_count": 0}
        assert progress["completed_work_items"] == {"count": 1, "previous_count": 0}
        assert logged[-1]["key"] == "2030-03-11"
        assert logged[-1]["count"] == 1

    def test_period_boundaries_are_exact_at_midnight(self, session_client, workspace, create_user):
        project, states = create_project(workspace, create_user, "Alpha", "ALP")
        with freeze_time("2030-03-13 12:00:00"):
            moments = [
                utc(2030, 3, 11, 23, 59, 59, 999999),  # two days ago: outside both periods
                utc(2030, 3, 12, 0, 0, 0),  # first instant of yesterday
                utc(2030, 3, 12, 23, 59, 59, 999999),  # last instant of yesterday
                utc(2030, 3, 13, 0, 0, 0),  # first instant of today
            ]
            for moment in moments:
                issue = create_issue(project, states, create_user, "completed")
                Issue.objects.filter(id=issue.id).update(created_at=moment, completed_at=moment)
            progress = session_client.get(
                ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "day"}
            ).data
            series = by_key(
                session_client.get(
                    CHARTS_URL.format(slug=workspace.slug), {"type": "work-items", "granularity": "day"}
                ).data["data"]
            )
        assert progress["created_work_items"] == {"count": 1, "previous_count": 2}
        assert progress["completed_work_items"] == {"count": 1, "previous_count": 2}
        assert [series[key]["created_issues"] for key in ("2030-03-11", "2030-03-12", "2030-03-13")] == [1, 2, 1]
        assert [series[key]["completed_issues"] for key in ("2030-03-11", "2030-03-12", "2030-03-13")] == [1, 2, 1]

    def test_week_and_month_series_cross_the_year_boundary(self, session_client, workspace, create_user):
        project, states = create_project(workspace, create_user, "Alpha", "ALP")
        with freeze_time("2030-01-15 12:00:00"):
            issue = create_issue(project, states, create_user, "started")
            # Sunday 30 Dec and Monday 31 Dec 2029 fall in different weeks but the same month.
            log_time(issue, create_user, 60, datetime(2029, 12, 30).date())
            log_time(issue, create_user, 120, datetime(2029, 12, 31).date())
            log_time(issue, create_user, 30, datetime(2030, 1, 1).date())
            weekly = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "week"}
            ).data["data"]
            monthly = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "month"}
            ).data["data"]
            spent = session_client.get(
                CHARTS_URL.format(slug=workspace.slug), {"type": "allocated-vs-spent", "granularity": "month"}
            ).data["data"]
        weeks, months = by_key(weekly), by_key(monthly)
        assert len(weekly) == 12
        assert weeks["2029-12-24"]["count"] == 1
        assert weeks["2029-12-31"]["count"] == 2.5
        assert [item["key"] for item in monthly][0] == "2029-02-01"
        assert [item["key"] for item in monthly][-1] == "2030-01-01"
        assert len(monthly) == 12
        assert months["2029-12-01"]["count"] == 3
        assert months["2030-01-01"]["count"] == 0.5
        assert by_key(spent)["2029-12-01"]["spent_hours"] == 3

    def test_week_progress_compares_monday_to_sunday_weeks(self, session_client, workspace, create_user):
        project, states = create_project(workspace, create_user, "Alpha", "ALP")
        # Wednesday 13 Mar 2030: this week is 11-17 Mar, last week 4-10 Mar.
        with freeze_time("2030-03-13 12:00:00"):
            issue = create_issue(project, states, create_user, "started")
            teammate = User.objects.create(email="teammate@plane.so", username="teammate")
            log_time(issue, create_user, 60, datetime(2030, 3, 11).date())
            log_time(issue, create_user, 30, datetime(2030, 3, 10).date())
            log_time(issue, teammate, 90, datetime(2030, 3, 4).date())
            log_time(issue, teammate, 600, datetime(2030, 3, 3).date())  # the week before last
            progress = session_client.get(
                ANALYTICS_URL.format(slug=workspace.slug), {"tab": "progress", "granularity": "week"}
            ).data
            totals = counts(
                session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data
            )
        assert progress["time_logged"] == {"count": 1, "previous_count": 2}
        assert progress["active_contributors"] == {"count": 1, "previous_count": 2}
        assert totals["time_logged_this_week"] == 1
        assert totals["time_logged_last_week"] == 2
        assert totals["contributors"] == 2


@pytest.mark.contract
@pytest.mark.django_db
class TestWorklogEdgeCases:
    @pytest.fixture
    def tracked(self, world):
        Project.objects.filter(id__in=[world["alpha"].id, world["beta"].id]).update(is_time_tracking_enabled=True)
        return world

    def url(self, workspace, project, issue, worklog=None):
        base = WORKLOGS_URL.format(slug=workspace.slug, project_id=project.id, issue_id=issue.id)
        return f"{base}{worklog.id}/" if worklog else base

    def test_cannot_log_time_through_another_projects_url(self, session_client, workspace, tracked):
        response = session_client.post(
            self.url(workspace, tracked["alpha"], tracked["beta_issue"]), {"duration": 30}, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert not IssueWorklog.objects.exists()

    def test_cannot_log_time_on_a_deleted_work_item(self, session_client, workspace, tracked):
        issue = tracked["alpha_issues"][0]
        Issue.objects.filter(id=issue.id).update(deleted_at=timezone.now())
        response = session_client.post(self.url(workspace, tracked["alpha"], issue), {"duration": 30}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("payload", [{}, {"duration": None}, {"duration": "an hour"}, {"duration": 1.5}])
    def test_duration_must_be_whole_minutes(self, session_client, workspace, tracked, payload):
        response = session_client.post(
            self.url(workspace, tracked["alpha"], tracked["alpha_issues"][0]), payload, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "duration" in response.data

    def test_logged_at_defaults_to_today_and_can_be_backdated(self, session_client, workspace, tracked):
        url = self.url(workspace, tracked["alpha"], tracked["alpha_issues"][0])
        default = session_client.post(url, {"duration": 30}, format="json")
        backdated = session_client.post(
            url, {"duration": 30, "logged_at": day_key(tracked["today"] - timedelta(days=40))}, format="json"
        )
        assert default.status_code == status.HTTP_201_CREATED
        assert default.data["logged_at"] == day_key(tracked["today"])
        assert backdated.data["logged_at"] == day_key(tracked["today"] - timedelta(days=40))
        # The backdated entry is outside the default 30-day series but still part of the totals.
        series = session_client.get(
            CHARTS_URL.format(slug=workspace.slug), {"type": "time-logged", "granularity": "day"}
        ).data["data"]
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data)
        assert sum(item["count"] for item in series) == 0.5
        assert totals["total_time_logged"] == 1

    def test_existing_entries_stay_readable_and_counted_after_tracking_is_disabled(
        self, session_client, workspace, create_user, tracked
    ):
        issue = tracked["alpha_issues"][0]
        worklog = log_time(issue, create_user, 60, tracked["today"])
        Project.objects.filter(id=tracked["alpha"].id).update(is_time_tracking_enabled=False)
        listing = session_client.get(self.url(workspace, tracked["alpha"], issue))
        update = session_client.patch(
            self.url(workspace, tracked["alpha"], issue, worklog), {"duration": 90}, format="json"
        )
        totals = counts(session_client.get(ANALYTICS_URL.format(slug=workspace.slug), {"tab": "time-tracking"}).data)
        assert [item["duration"] for item in listing.data] == [60]
        assert update.status_code == status.HTTP_400_BAD_REQUEST
        assert totals["total_time_logged"] == 1

    def test_worklog_of_another_work_item_is_not_reachable(self, session_client, workspace, create_user, tracked):
        first, second = tracked["alpha_issues"][:2]
        worklog = log_time(first, create_user, 60, tracked["today"])
        response = session_client.delete(self.url(workspace, tracked["alpha"], second, worklog))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert IssueWorklog.objects.filter(id=worklog.id).exists()
