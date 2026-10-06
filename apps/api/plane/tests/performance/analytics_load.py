# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Load test for the project / teamspace / time tracking analytics endpoints.

Seeds one large workspace, then replays a mix of analytics requests (unfiltered and filtered by
teamspace) at several concurrency levels and reports latency percentiles per endpoint.

Requests go through the full Django/DRF stack in-process (URL routing, permissions, views, ORM) from a
pool of threads, each with its own database connection, so the database sees real concurrent load.
There is no web server or network hop in the loop: the numbers are a lower bound on what a browser
sees and are meant for comparing changes and spotting slow query plans, not for capacity planning.

This is not collected by pytest. Run it against a throwaway, migrated database, e.g. with the test stack:

    docker compose -f docker-compose-test.yml run --rm api-tests sh -c \\
        "python manage.py migrate && python -m plane.tests.performance.analytics_load"

Options: --issues, --projects, --worklogs, --members, --concurrency 1,8,32, --requests, --skip-seed
(reuse the data from a previous run), --explain (print the plan of each endpoint's slowest query).
"""

import argparse
import os
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "plane.settings.test")
django.setup()

from django.db import connection, connections  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from plane.db.models import (  # noqa: E402
    Estimate,
    EstimatePoint,
    Issue,
    IssueAssignee,
    IssueWorklog,
    Project,
    ProjectMember,
    State,
    Teamspace,
    TeamspaceMember,
    TeamspaceProject,
    User,
    Workspace,
    WorkspaceMember,
)

SLUG = "analytics-load"
STATE_GROUPS = ["backlog", "unstarted", "started", "completed", "cancelled"]
BATCH = 5000


def bulk(model, rows):
    for start in range(0, len(rows), BATCH):
        model.objects.bulk_create(rows[start : start + BATCH])


def seed(options):
    random.seed(42)
    today = timezone.localdate()
    owner = User.objects.create(email="load-owner@plane.so", username="load-owner", display_name="owner")
    members = [owner] + [
        User.objects.create(email=f"load-{index}@plane.so", username=f"load-{index}", display_name=f"member-{index}")
        for index in range(options.members - 1)
    ]
    workspace = Workspace.objects.create(name="Analytics load", slug=SLUG, owner=owner)
    bulk(WorkspaceMember, [WorkspaceMember(workspace=workspace, member=member, role=20) for member in members])

    projects, states, time_points = [], {}, {}
    for index in range(options.projects):
        project = Project.objects.create(
            name=f"Project {index}", identifier=f"L{index}", workspace=workspace, is_time_tracking_enabled=True
        )
        projects.append(project)
        states[project.id] = [State.objects.create(name=group, project=project, group=group) for group in STATE_GROUPS]
        estimate = Estimate.objects.create(name="Hours", type="time", project=project)
        time_points[project.id] = [
            EstimatePoint.objects.create(estimate=estimate, key=key, value=str(minutes), project=project)
            for key, minutes in enumerate((30, 60, 120, 240, 480), start=1)
        ]
    bulk(
        ProjectMember,
        [
            ProjectMember(project=project, member=member, workspace=workspace, role=20)
            for project in projects
            for member in members
        ],
    )

    # Teamspaces of eight projects each, overlapping by four so shared projects are exercised.
    teamspaces = []
    for index, start in enumerate(range(0, max(options.projects - 4, 1), 4)):
        teamspace = Teamspace.objects.create(name=f"Teamspace {index}", workspace=workspace, lead=owner)
        teamspaces.append(teamspace)
        bulk(
            TeamspaceProject,
            [
                TeamspaceProject(teamspace=teamspace, project=project, workspace=workspace)
                for project in projects[start : start + 8]
            ],
        )
        bulk(
            TeamspaceMember,
            [TeamspaceMember(teamspace=teamspace, member=member, workspace=workspace) for member in members[:5]],
        )

    # Skewed sizes: a handful of very large projects and a long tail, as in real workspaces.
    issues = []
    for index in range(options.issues):
        project = projects[min(int(random.expovariate(0.12)), options.projects - 1)]
        issues.append(
            Issue(
                name=f"Work item {index}",
                workspace=workspace,
                project=project,
                state=random.choice(states[project.id]),
                estimate_point=random.choice(time_points[project.id]) if random.random() < 0.4 else None,
                target_date=today - timedelta(days=random.randint(-30, 400)) if random.random() < 0.5 else None,
                created_by=owner,
                sequence_id=index + 1,
            )
        )
    bulk(Issue, issues)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE issues SET created_at = now() - random() * interval '720 days' WHERE workspace_id = %s",
            [workspace.id],
        )
        cursor.execute(
            """
            UPDATE issues i SET completed_at = LEAST(now(), i.created_at + random() * interval '60 days')
            FROM states s WHERE s.id = i.state_id AND s."group" = 'completed' AND i.workspace_id = %s
            """,
            [workspace.id],
        )

    sample = random.sample(issues, min(len(issues), max(options.worklogs // 4, 1)))
    bulk(
        IssueAssignee,
        [
            IssueAssignee(
                issue=issue, assignee=random.choice(members), project_id=issue.project_id, workspace=workspace
            )
            for issue in sample
        ],
    )
    bulk(
        IssueWorklog,
        [
            IssueWorklog(
                issue=issue,
                project_id=issue.project_id,
                workspace=workspace,
                logged_by=random.choice(members),
                duration=random.randint(5, 240),
                logged_at=today - timedelta(days=random.randint(0, 720)),
            )
            for issue in random.choices(sample, k=options.worklogs)
        ],
    )
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE")
    print(
        f"seeded: {options.projects} projects, {len(issues)} work items, {options.worklogs} worklogs, "
        f"{len(teamspaces)} teamspaces, {len(members)} members"
    )


def scenarios(workspace):
    base = f"/api/workspaces/{workspace.slug}"
    requests = {
        "summary projects": ("advance-analytics", {"tab": "projects"}),
        "summary time-tracking": ("advance-analytics", {"tab": "time-tracking"}),
        "summary progress (week)": ("advance-analytics", {"tab": "progress", "granularity": "week"}),
        "table projects": ("advance-analytics-stats", {"type": "projects"}),
        "table members": ("advance-analytics-stats", {"type": "time-tracking"}),
        "table teamspaces": ("advance-analytics-stats", {"type": "teamspaces"}),
        "chart created-vs-resolved (week)": ("advance-analytics-charts", {"type": "work-items", "granularity": "week"}),
        "chart project distribution": ("advance-analytics-charts", {"type": "project-distribution"}),
        "chart time logged (week)": ("advance-analytics-charts", {"type": "time-logged", "granularity": "week"}),
        "chart allocated-vs-spent (week)": (
            "advance-analytics-charts",
            {"type": "allocated-vs-spent", "granularity": "week"},
        ),
    }
    # The teamspace holding the largest projects, plus one from the long tail.
    teamspaces = list(Teamspace.objects.filter(workspace=workspace).order_by("created_at"))
    filters = {"all projects": {}}
    if teamspaces:
        filters["largest teamspace"] = {"teamspace_ids": str(teamspaces[0].id)}
        filters["two teamspaces"] = {"teamspace_ids": f"{teamspaces[0].id},{teamspaces[-1].id}"}
    return [
        (name, scope, f"{base}/{path}/", {**params, **extra})
        for name, (path, params) in requests.items()
        for scope, extra in filters.items()
    ]


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def run_level(user, plan, concurrency, total_requests):
    work = [plan[index % len(plan)] for index in range(total_requests)]
    random.Random(concurrency).shuffle(work)

    def worker(chunk):
        client = APIClient()
        client.force_authenticate(user=user)
        results = []
        try:
            for name, scope, url, params in chunk:
                started = time.perf_counter()
                response = client.get(url, params)
                results.append((name, scope, (time.perf_counter() - started) * 1000, response.status_code))
        finally:
            connections.close_all()
        return results

    chunks = [work[index::concurrency] for index in range(concurrency)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = [row for chunk in pool.map(worker, chunks) for row in chunk]
    elapsed = time.perf_counter() - started

    errors = [row for row in results if row[3] != 200]
    print(
        f"\n## concurrency {concurrency}: {len(results)} requests in {elapsed:.1f}s "
        f"({len(results) / elapsed:.1f} req/s), {len(errors)} errors"
    )
    print(f"{'endpoint':34} {'scope':18} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    grouped = {}
    for name, scope, duration, _ in results:
        grouped.setdefault((name, scope), []).append(duration)
    for (name, scope), durations in grouped.items():
        print(
            f"{name:34} {scope:18} {statistics.median(durations):8.0f} "
            f"{percentile(durations, 0.95):8.0f} {max(durations):8.0f}"
        )
    everything = [row[2] for row in results]
    print(
        f"{'ALL':34} {'':18} {statistics.median(everything):8.0f} "
        f"{percentile(everything, 0.95):8.0f} {max(everything):8.0f}"
    )
    return len(errors)


def explain(user, plan):
    """Print the query count of every endpoint and the plan of its slowest query."""
    client = APIClient()
    client.force_authenticate(user=user)
    for name, scope, url, params in plan:
        with CaptureQueriesContext(connection) as context:
            client.get(url, params)
        slowest = max(context.captured_queries, key=lambda query: float(query["time"]))
        print(f"\n### {name} [{scope}]: {len(context.captured_queries)} queries, slowest {slowest['time']}s")
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + slowest["sql"])
            print("\n".join(row[0] for row in cursor.fetchall()))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issues", type=int, default=400_000)
    parser.add_argument("--projects", type=int, default=40)
    parser.add_argument("--worklogs", type=int, default=300_000)
    parser.add_argument("--members", type=int, default=25)
    parser.add_argument("--concurrency", default="1,8,32")
    parser.add_argument("--requests", type=int, default=600, help="requests per concurrency level")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--explain", action="store_true")
    options = parser.parse_args()

    if not options.skip_seed:
        if Workspace.objects.filter(slug=SLUG).exists():
            parser.error(f"workspace '{SLUG}' already exists; pass --skip-seed to reuse it")
        seed(options)
    workspace = Workspace.objects.get(slug=SLUG)
    user = workspace.owner
    plan = scenarios(workspace)

    if options.explain:
        explain(user, plan)
        return
    errors = 0
    for concurrency in [int(value) for value in options.concurrency.split(",")]:
        errors += run_level(user, plan, concurrency, options.requests)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
