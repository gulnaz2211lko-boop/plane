# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from plane.db.models import IssueWorklog


class IssueWorklogSerializer(BaseSerializer):
    duration = serializers.IntegerField(min_value=1)

    class Meta:
        model = IssueWorklog
        fields = [
            "id",
            "issue_id",
            "project_id",
            "workspace_id",
            "logged_by_id",
            "duration",
            "logged_at",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "issue_id",
            "project_id",
            "workspace_id",
            "logged_by_id",
            "created_at",
            "updated_at",
        ]
