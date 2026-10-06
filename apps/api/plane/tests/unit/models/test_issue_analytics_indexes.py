# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The analytics indexes on the issues table must be created without blocking writes."""

from importlib import import_module

import pytest
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import connection, migrations

from plane.db.models import Issue

INDEX_NAMES = {"issue_project_created_at_idx", "issue_project_completed_at_idx", "issue_project_deleted_idx"}


@pytest.mark.unit
class TestIssueAnalyticsIndexMigration:
    @pytest.fixture
    def migration(self):
        return import_module("plane.db.migrations.0125_issue_analytics_indexes").Migration

    def test_runs_outside_a_transaction(self, migration):
        # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
        assert migration.atomic is False

    def test_every_index_is_built_concurrently(self, migration):
        index_operations = [op for op in migration.operations if isinstance(op, migrations.AddIndex)]
        assert {op.index.name for op in index_operations} == INDEX_NAMES
        assert all(isinstance(op, AddIndexConcurrently) for op in index_operations)

    def test_leftover_invalid_index_is_dropped_before_each_build(self, migration):
        operations = migration.operations
        for position, operation in enumerate(operations):
            if isinstance(operation, AddIndexConcurrently):
                previous = operations[position - 1]
                assert isinstance(previous, migrations.RunSQL)
                assert previous.sql == f'DROP INDEX CONCURRENTLY IF EXISTS "{operation.index.name}";'

    def test_model_declares_the_same_indexes(self):
        assert {index.name for index in Issue._meta.indexes} == INDEX_NAMES


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueAnalyticsIndexesInDatabase:
    def test_indexes_exist_and_are_valid(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.relname, i.indisvalid, pg_get_indexdef(i.indexrelid)
                FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = ANY(%s)
                """,
                [list(INDEX_NAMES)],
            )
            rows = {name: (valid, definition) for name, valid, definition in cursor.fetchall()}
        assert set(rows) == INDEX_NAMES
        assert all(valid for valid, _ in rows.values())
        assert "(project_id, created_at)" in rows["issue_project_created_at_idx"][1]
        assert "WHERE (completed_at IS NOT NULL)" in rows["issue_project_completed_at_idx"][1]
        assert "WHERE (deleted_at IS NOT NULL)" in rows["issue_project_deleted_idx"][1]
