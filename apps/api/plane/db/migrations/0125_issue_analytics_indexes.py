# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # Built concurrently so the issues table stays writable while the indexes are created.
    atomic = False

    dependencies = [
        ("db", "0124_estimate_type_time"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="issue",
            index=models.Index(fields=["project", "created_at"], name="issue_project_created_at_idx"),
        ),
        AddIndexConcurrently(
            model_name="issue",
            index=models.Index(
                condition=models.Q(("completed_at__isnull", False)),
                fields=["project", "completed_at"],
                name="issue_project_completed_at_idx",
            ),
        ),
    ]
