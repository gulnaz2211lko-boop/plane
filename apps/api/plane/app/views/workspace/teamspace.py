# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Prefetch

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import TeamspaceSerializer
from plane.app.views.base import BaseViewSet
from plane.db.models import Teamspace, TeamspaceProject, Workspace


class TeamspaceViewSet(BaseViewSet):
    serializer_class = TeamspaceSerializer
    model = Teamspace

    def get_queryset(self):
        return (
            Teamspace.objects.filter(workspace__slug=self.kwargs.get("slug"))
            .prefetch_related(
                "teamspace_members",
                Prefetch(
                    "teamspace_projects",
                    queryset=TeamspaceProject.objects.select_related("project"),
                ),
            )
            .order_by("name")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace_id"] = Workspace.objects.get(slug=self.kwargs.get("slug")).id
        return context

    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def list(self, request, slug):
        serializer = TeamspaceSerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def retrieve(self, request, slug, pk):
        teamspace = self.get_queryset().filter(pk=pk).first()
        if teamspace is None:
            return Response({"error": "Teamspace not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TeamspaceSerializer(teamspace).data, status=status.HTTP_200_OK)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def create(self, request, slug):
        serializer = TeamspaceSerializer(data=request.data, context=self.get_serializer_context())
        if serializer.is_valid():
            teamspace = serializer.save()
            teamspace = self.get_queryset().get(pk=teamspace.pk)
            return Response(TeamspaceSerializer(teamspace).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def partial_update(self, request, slug, pk):
        teamspace = self.get_queryset().filter(pk=pk).first()
        if teamspace is None:
            return Response({"error": "Teamspace not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TeamspaceSerializer(
            teamspace, data=request.data, partial=True, context=self.get_serializer_context()
        )
        if serializer.is_valid():
            serializer.save()
            teamspace = self.get_queryset().get(pk=pk)
            return Response(TeamspaceSerializer(teamspace).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission(allowed_roles=[ROLE.ADMIN], level="WORKSPACE")
    def destroy(self, request, slug, pk):
        teamspace = self.get_queryset().filter(pk=pk).first()
        if teamspace is None:
            return Response({"error": "Teamspace not found"}, status=status.HTTP_404_NOT_FOUND)
        teamspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
