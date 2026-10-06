# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for workspace teamspaces CRUD and permissions."""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Project, Teamspace, TeamspaceMember, TeamspaceProject, User, WorkspaceMember

LIST_URL = "/api/workspaces/{slug}/teamspaces/"
DETAIL_URL = "/api/workspaces/{slug}/teamspaces/{pk}/"


def make_member(workspace, role):
    unique_id = uuid4().hex[:8]
    user = User.objects.create(email=f"member-{unique_id}@plane.so", username=f"member_{unique_id}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, client


@pytest.fixture
def projects(db, workspace, create_user):
    return [
        Project.objects.create(name=f"Project {i}", identifier=f"PR{i}", workspace=workspace, created_by=create_user)
        for i in range(2)
    ]


@pytest.mark.contract
@pytest.mark.django_db
class TestTeamspaceCRUD:
    def test_admin_creates_teamspace_with_members_and_projects(self, session_client, workspace, create_user, projects):
        member, _ = make_member(workspace, role=15)
        response = session_client.post(
            LIST_URL.format(slug=workspace.slug),
            {
                "name": "Platform",
                "description": "Platform team",
                "lead_id": str(create_user.id),
                "member_ids": [str(create_user.id), str(member.id)],
                "project_ids": [str(projects[0].id)],
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        data = response.data
        assert data["name"] == "Platform"
        assert data["lead_id"] == str(create_user.id)
        assert sorted(data["member_ids"]) == sorted([str(create_user.id), str(member.id)])
        assert data["project_ids"] == [str(projects[0].id)]
        assert data["workspace"] == workspace.id

    def test_list_and_retrieve_for_member(self, workspace, projects):
        teamspace = Teamspace.objects.create(name="Design", workspace=workspace)
        TeamspaceProject.objects.create(teamspace=teamspace, project=projects[1], workspace=workspace)
        _, member_client = make_member(workspace, role=15)

        list_response = member_client.get(LIST_URL.format(slug=workspace.slug))
        assert list_response.status_code == status.HTTP_200_OK
        assert [item["name"] for item in list_response.data] == ["Design"]
        assert list_response.data[0]["project_ids"] == [str(projects[1].id)]

        detail_response = member_client.get(DETAIL_URL.format(slug=workspace.slug, pk=teamspace.id))
        assert detail_response.status_code == status.HTTP_200_OK
        assert str(detail_response.data["id"]) == str(teamspace.id)

    def test_partial_update_replaces_member_and_project_sets(self, session_client, workspace, create_user, projects):
        member, _ = make_member(workspace, role=15)
        teamspace = Teamspace.objects.create(name="Core", workspace=workspace)
        TeamspaceMember.objects.create(teamspace=teamspace, member=create_user, workspace=workspace)
        TeamspaceProject.objects.create(teamspace=teamspace, project=projects[0], workspace=workspace)

        response = session_client.patch(
            DETAIL_URL.format(slug=workspace.slug, pk=teamspace.id),
            {"member_ids": [str(member.id)], "project_ids": [str(projects[1].id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["member_ids"] == [str(member.id)]
        assert response.data["project_ids"] == [str(projects[1].id)]
        assert response.data["name"] == "Core"

    def test_duplicate_name_is_rejected(self, session_client, workspace):
        Teamspace.objects.create(name="Core", workspace=workspace)
        response = session_client.post(LIST_URL.format(slug=workspace.slug), {"name": "Core"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_non_workspace_member_and_foreign_project_are_rejected(self, session_client, workspace, create_user):
        outsider = User.objects.create(email="outsider@plane.so", username="outsider")
        response = session_client.post(
            LIST_URL.format(slug=workspace.slug),
            {"name": "Bad", "member_ids": [str(outsider.id)], "project_ids": [str(uuid4())]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "member_ids" in response.data
        assert "project_ids" in response.data

    @mock.patch("plane.db.mixins.soft_delete_related_objects")
    def test_admin_deletes_teamspace(self, _soft_delete, session_client, workspace):
        teamspace = Teamspace.objects.create(name="Temp", workspace=workspace)
        response = session_client.delete(DETAIL_URL.format(slug=workspace.slug, pk=teamspace.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Teamspace.objects.filter(id=teamspace.id).exists()

    def test_member_cannot_write(self, workspace):
        teamspace = Teamspace.objects.create(name="Locked", workspace=workspace)
        _, member_client = make_member(workspace, role=15)

        create = member_client.post(LIST_URL.format(slug=workspace.slug), {"name": "Nope"}, format="json")
        update = member_client.patch(
            DETAIL_URL.format(slug=workspace.slug, pk=teamspace.id), {"name": "Renamed"}, format="json"
        )
        delete = member_client.delete(DETAIL_URL.format(slug=workspace.slug, pk=teamspace.id))

        assert create.status_code == status.HTTP_403_FORBIDDEN
        assert update.status_code == status.HTTP_403_FORBIDDEN
        assert delete.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_cannot_list(self, workspace):
        _, guest_client = make_member(workspace, role=5)
        response = guest_client.get(LIST_URL.format(slug=workspace.slug))
        assert response.status_code == status.HTTP_403_FORBIDDEN
