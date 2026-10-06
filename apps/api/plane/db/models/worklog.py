# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# Module imports
from .project import ProjectBaseModel


class IssueWorklog(ProjectBaseModel):
    issue = models.ForeignKey("db.Issue", on_delete=models.CASCADE, related_name="worklogs")
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="worklogs")
    # duration in minutes
    duration = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    logged_at = models.DateField(default=timezone.localdate)
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.issue.name} <{self.logged_by.email}> {self.duration}m"

    class Meta:
        verbose_name = "Issue Worklog"
        verbose_name_plural = "Issue Worklogs"
        db_table = "issue_worklogs"
        ordering = ("-logged_at", "-created_at")
        indexes = [models.Index(fields=["project", "logged_at"], name="worklog_project_logged_at_idx")]
