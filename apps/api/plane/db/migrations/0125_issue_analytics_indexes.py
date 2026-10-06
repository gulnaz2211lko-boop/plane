# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


def drop_leftover(name):
    """
    CREATE INDEX CONCURRENTLY leaves an INVALID index behind when it is interrupted, and a retry would
    then fail with "already exists". Dropping any leftover first makes the migration safe to re-run.
    """
    return migrations.RunSQL(
        sql=f'DROP INDEX CONCURRENTLY IF EXISTS "{name}";',
        reverse_sql=migrations.RunSQL.noop,
    )


class Migration(migrations.Migration):
    # Built concurrently (so outside a transaction): the issues table stays readable and writable
    # while the indexes are created, at the cost of a slower build.
    atomic = False

    dependencies = [
        ("db", "0124_estimate_type_time"),
    ]

    operations = [
        drop_leftover("issue_project_created_at_idx"),
        AddIndexConcurrently(
            model_name="issue",
            index=models.Index(fields=["project", "created_at"], name="issue_project_created_at_idx"),
        ),
        drop_leftover("issue_project_completed_at_idx"),
        AddIndexConcurrently(
            model_name="issue",
            index=models.Index(
                condition=models.Q(("completed_at__isnull", False)),
                fields=["project", "completed_at"],
                name="issue_project_completed_at_idx",
            ),
        ),
        drop_leftover("issue_project_deleted_idx"),
        AddIndexConcurrently(
            model_name="issue",
            index=models.Index(
                condition=models.Q(("deleted_at__isnull", False)),
                fields=["project"],
                name="issue_project_deleted_idx",
            ),
        ),
    ]
