# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for work item worklogs (time tracking)."""

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueWorklog, Project, ProjectMember, State, User, WorkspaceMember


def worklogs_url(workspace, project, issue, pk=None):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/worklogs/"
    return f"{url}{pk}/" if pk else url


@pytest.fixture
def setup(db, workspace, create_user):
    project = Project.objects.create(
        name="Tracked", identifier="TRK", workspace=workspace, created_by=create_user, is_time_tracking_enabled=True
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
    state = State.objects.create(name="Todo", project=project, group="backlog", default=True)
    issue = Issue.objects.create(name="Task", workspace=workspace, project=project, state=state, created_by=create_user)
    return project, issue


def project_member_client(workspace, project, role=15):
    unique_id = uuid4().hex[:8]
    user = User.objects.create(email=f"pm-{unique_id}@plane.so", username=f"pm_{unique_id}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


@pytest.mark.contract
@pytest.mark.django_db
class TestIssueWorklogs:
    def test_create_and_list(self, session_client, workspace, create_user, setup):
        project, issue = setup
        response = session_client.post(
            worklogs_url(workspace, project, issue),
            {"duration": 90, "logged_at": "2026-10-01", "description": "Pairing"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data["duration"] == 90
        assert response.data["logged_at"] == "2026-10-01"
        assert response.data["logged_by_id"] == create_user.id
        assert response.data["issue_id"] == issue.id

        list_response = session_client.get(worklogs_url(workspace, project, issue))
        assert list_response.status_code == status.HTTP_200_OK
        assert [item["duration"] for item in list_response.data] == [90]

    def test_logged_by_cannot_be_spoofed(self, session_client, workspace, create_user, setup):
        project, issue = setup
        other, _ = project_member_client(workspace, project)
        response = session_client.post(
            worklogs_url(workspace, project, issue), {"duration": 15, "logged_by_id": str(other.id)}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert IssueWorklog.objects.get(id=response.data["id"]).logged_by_id == create_user.id

    def test_rejected_when_time_tracking_disabled(self, session_client, workspace, setup):
        project, issue = setup
        project.is_time_tracking_enabled = False
        project.save()
        response = session_client.post(worklogs_url(workspace, project, issue), {"duration": 30}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Time tracking is not enabled for this project"

    def test_rejects_non_positive_duration(self, session_client, workspace, setup):
        project, issue = setup
        response = session_client.post(worklogs_url(workspace, project, issue), {"duration": 0}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "duration" in response.data

    def test_owner_can_update_and_delete(self, workspace, setup):
        project, issue = setup
        user, client = project_member_client(workspace, project)
        worklog = IssueWorklog.objects.create(issue=issue, project=project, logged_by=user, duration=30)

        update = client.patch(worklogs_url(workspace, project, issue, worklog.id), {"duration": 45}, format="json")
        assert update.status_code == status.HTTP_200_OK
        assert update.data["duration"] == 45

        delete = client.delete(worklogs_url(workspace, project, issue, worklog.id))
        assert delete.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueWorklog.all_objects.filter(id=worklog.id).exists()

    def test_non_owner_member_cannot_modify(self, workspace, create_user, setup):
        project, issue = setup
        worklog = IssueWorklog.objects.create(issue=issue, project=project, logged_by=create_user, duration=30)
        _, client = project_member_client(workspace, project)

        update = client.patch(worklogs_url(workspace, project, issue, worklog.id), {"duration": 1}, format="json")
        delete = client.delete(worklogs_url(workspace, project, issue, worklog.id))

        assert update.status_code == status.HTTP_403_FORBIDDEN
        assert delete.status_code == status.HTTP_403_FORBIDDEN
        assert IssueWorklog.objects.get(id=worklog.id).duration == 30

    def test_project_admin_can_delete_others_worklog(self, session_client, workspace, setup):
        project, issue = setup
        user, _ = project_member_client(workspace, project)
        worklog = IssueWorklog.objects.create(issue=issue, project=project, logged_by=user, duration=30)

        response = session_client.delete(worklogs_url(workspace, project, issue, worklog.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_guest_can_read_but_not_log(self, workspace, setup):
        project, issue = setup
        _, guest_client = project_member_client(workspace, project, role=5)

        assert guest_client.get(worklogs_url(workspace, project, issue)).status_code == status.HTTP_200_OK
        response = guest_client.post(worklogs_url(workspace, project, issue), {"duration": 10}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_project_list_exposes_time_tracking_flag(self, session_client, workspace, setup):
        project, _ = setup
        response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/")
        assert response.status_code == status.HTTP_200_OK
        row = next(item for item in response.data if item["id"] == project.id)
        assert row["is_time_tracking_enabled"] is True
