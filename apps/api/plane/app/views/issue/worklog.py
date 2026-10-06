# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueWorklogSerializer
from plane.app.views.base import BaseViewSet
from plane.db.models import Issue, IssueWorklog, Project, ProjectMember

TIME_TRACKING_DISABLED_ERROR = {"error": "Time tracking is not enabled for this project"}


class IssueWorklogViewSet(BaseViewSet):
    serializer_class = IssueWorklogSerializer
    model = IssueWorklog

    def get_queryset(self):
        return IssueWorklog.objects.filter(
            workspace__slug=self.kwargs.get("slug"),
            project_id=self.kwargs.get("project_id"),
            issue_id=self.kwargs.get("issue_id"),
            project__archived_at__isnull=True,
        ).order_by("-logged_at", "-created_at")

    def _is_time_tracking_enabled(self, slug, project_id):
        return Project.objects.filter(workspace__slug=slug, pk=project_id, is_time_tracking_enabled=True).exists()

    def _can_modify(self, request, worklog, slug, project_id):
        if worklog.logged_by_id == request.user.id:
            return True
        return ProjectMember.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            member=request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id, issue_id):
        serializer = IssueWorklogSerializer(self.get_queryset(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def create(self, request, slug, project_id, issue_id):
        if not self._is_time_tracking_enabled(slug, project_id):
            return Response(TIME_TRACKING_DISABLED_ERROR, status=status.HTTP_400_BAD_REQUEST)
        if not Issue.issue_objects.filter(workspace__slug=slug, project_id=project_id, pk=issue_id).exists():
            return Response({"error": "Work item not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = IssueWorklogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=project_id, issue_id=issue_id, logged_by_id=request.user.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def partial_update(self, request, slug, project_id, issue_id, pk):
        if not self._is_time_tracking_enabled(slug, project_id):
            return Response(TIME_TRACKING_DISABLED_ERROR, status=status.HTTP_400_BAD_REQUEST)
        worklog = self.get_queryset().filter(pk=pk).first()
        if worklog is None:
            return Response({"error": "Worklog not found"}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_modify(request, worklog, slug, project_id):
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = IssueWorklogSerializer(worklog, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def destroy(self, request, slug, project_id, issue_id, pk):
        worklog = self.get_queryset().filter(pk=pk).first()
        if worklog is None:
            return Response({"error": "Worklog not found"}, status=status.HTTP_404_NOT_FOUND)
        if not self._can_modify(request, worklog, slug, project_id):
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        worklog.delete(soft=False)
        return Response(status=status.HTTP_204_NO_CONTENT)
