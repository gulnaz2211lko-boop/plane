# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import (
    Project,
    Teamspace,
    TeamspaceMember,
    TeamspaceProject,
    WorkspaceMember,
)


class TeamspaceSerializer(BaseSerializer):
    lead_id = serializers.UUIDField(required=False, allow_null=True)
    member_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    project_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    class Meta:
        model = Teamspace
        fields = [
            "id",
            "name",
            "description",
            "logo_props",
            "lead_id",
            "member_ids",
            "project_ids",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "created_at", "updated_at"]

    def _workspace_id(self):
        return self.context["workspace_id"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name is required")
        queryset = Teamspace.objects.filter(workspace_id=self._workspace_id(), name=name)
        if self.instance is not None:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A teamspace with this name already exists")
        return name

    def _validate_members(self, member_ids):
        valid_ids = set(
            WorkspaceMember.objects.filter(
                workspace_id=self._workspace_id(),
                member_id__in=member_ids,
                is_active=True,
                member__is_bot=False,
            ).values_list("member_id", flat=True)
        )
        invalid = [str(member_id) for member_id in member_ids if member_id not in valid_ids]
        if invalid:
            raise serializers.ValidationError(f"Not active workspace members: {', '.join(invalid)}")

    def validate_lead_id(self, value):
        if value is not None:
            self._validate_members([value])
        return value

    def validate_member_ids(self, value):
        value = list(dict.fromkeys(value))
        self._validate_members(value)
        return value

    def validate_project_ids(self, value):
        value = list(dict.fromkeys(value))
        valid_ids = set(
            Project.objects.filter(
                workspace_id=self._workspace_id(), id__in=value, archived_at__isnull=True
            ).values_list("id", flat=True)
        )
        invalid = [str(project_id) for project_id in value if project_id not in valid_ids]
        if invalid:
            raise serializers.ValidationError(f"Invalid projects: {', '.join(invalid)}")
        return value

    def _sync_members(self, teamspace, member_ids):
        existing = TeamspaceMember.objects.filter(teamspace=teamspace)
        existing.exclude(member_id__in=member_ids).delete(soft=False)
        current = set(existing.values_list("member_id", flat=True))
        TeamspaceMember.objects.bulk_create(
            [
                TeamspaceMember(
                    teamspace=teamspace,
                    member_id=member_id,
                    workspace_id=teamspace.workspace_id,
                    created_by_id=teamspace.updated_by_id or teamspace.created_by_id,
                )
                for member_id in member_ids
                if member_id not in current
            ]
        )

    def _sync_projects(self, teamspace, project_ids):
        existing = TeamspaceProject.objects.filter(teamspace=teamspace)
        existing.exclude(project_id__in=project_ids).delete(soft=False)
        current = set(existing.values_list("project_id", flat=True))
        TeamspaceProject.objects.bulk_create(
            [
                TeamspaceProject(
                    teamspace=teamspace,
                    project_id=project_id,
                    workspace_id=teamspace.workspace_id,
                    created_by_id=teamspace.updated_by_id or teamspace.created_by_id,
                )
                for project_id in project_ids
                if project_id not in current
            ]
        )

    def _save_relations(self, teamspace, member_ids, project_ids):
        if member_ids is not None:
            self._sync_members(teamspace, member_ids)
        if project_ids is not None:
            self._sync_projects(teamspace, project_ids)

    def create(self, validated_data):
        member_ids = validated_data.pop("member_ids", None)
        project_ids = validated_data.pop("project_ids", None)
        teamspace = Teamspace.objects.create(workspace_id=self._workspace_id(), **validated_data)
        self._save_relations(teamspace, member_ids, project_ids)
        return teamspace

    def update(self, instance, validated_data):
        member_ids = validated_data.pop("member_ids", None)
        project_ids = validated_data.pop("project_ids", None)
        instance = super().update(instance, validated_data)
        self._save_relations(instance, member_ids, project_ids)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["lead_id"] = str(instance.lead_id) if instance.lead_id else None
        # The list endpoint prefetches these; fall back to a query for single objects.
        data["member_ids"] = [
            str(teamspace_member.member_id)
            for teamspace_member in instance.teamspace_members.all()
            if teamspace_member.deleted_at is None
        ]
        data["project_ids"] = [
            str(teamspace_project.project_id)
            for teamspace_project in instance.teamspace_projects.all()
            if teamspace_project.deleted_at is None and teamspace_project.project.deleted_at is None
        ]
        return data
