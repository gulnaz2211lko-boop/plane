/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane package imports
import { ProjectsOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { ProjectInsightColumns } from "@plane/types";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
import { useProject } from "@/hooks/store/use-project";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local imports
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import { exportCSV } from "../export";
import { formatHours, formatPercent } from "../format";
import { InsightTable } from "../insight-table";
import TrendPiece from "../trend-piece";
import { WorkItemsModal } from "../work-items/modal";

const analyticsService = new AnalyticsService();

type TNumericColumn = Exclude<keyof ProjectInsightColumns, "project_id" | "project__name" | "teamspace_ids">;

const ProjectsInsightTable = observer(function ProjectsInsightTable() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  // state
  const [peekProjectId, setPeekProjectId] = useState<string | null>(null);
  // store hooks
  const { getProjectById } = useProject();
  const { filterParams, filtersKey, isPeekView } = useAnalytics();

  const { data, isLoading } = useSWR(
    workspaceSlug ? `insights-table-projects-${workspaceSlug}-${filtersKey}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsStats<ProjectInsightColumns[]>(
        workspaceSlug!.toString(),
        "projects",
        filterParams,
        isPeekView
      )
  );

  const columns: ColumnDef<ProjectInsightColumns>[] = useMemo(() => {
    const numericColumn = (
      key: TNumericColumn,
      label: string,
      render: (row: ProjectInsightColumns) => React.ReactNode = (row) => row[key] ?? "-",
      exportValue: (row: ProjectInsightColumns) => string | number = (row) => row[key] ?? ""
    ): ColumnDef<ProjectInsightColumns> => ({
      accessorKey: key,
      header: () => <div className="text-right">{label}</div>,
      cell: ({ row }) => <div className="flex justify-end text-right">{render(row.original)}</div>,
      meta: { export: { key: label, value: (row) => exportValue(row.original) } },
    });

    return [
      {
        accessorKey: "project__name",
        header: () => <div className="text-left">{t("common.project")}</div>,
        cell: ({ row }) => {
          const project = getProjectById(row.original.project_id);
          return (
            <button
              type="button"
              className="flex items-center gap-2 text-left hover:underline"
              onClick={() => setPeekProjectId(row.original.project_id)}
            >
              {project?.logo_props ? (
                <Logo logo={project.logo_props} size={18} />
              ) : (
                <ProjectsOutline className="h-4 w-4" />
              )}
              {project?.name ?? row.original.project__name}
            </button>
          );
        },
        meta: { export: { key: t("common.project"), value: (row) => row.original.project__name } },
      },
      numericColumn("total_work_items", t("workspace_analytics.projects.columns.total")),
      numericColumn("completed_work_items", t("workspace_projects.state.completed")),
      numericColumn("pending_work_items", t("workspace_analytics.projects.pending")),
      numericColumn("overdue_work_items", t("workspace_analytics.projects.overdue")),
      numericColumn(
        "completion_percentage",
        t("workspace_analytics.projects.columns.completion"),
        (row) => (
          <TrendPiece percentage={row.completion_percentage} size="xs" variant="tinted" trendIconVisible={false} />
        ),
        (row) => `${row.completion_percentage}%`
      ),
      numericColumn("total_members", t("common.members")),
      numericColumn("total_cycles", t("common.cycles")),
      numericColumn("total_modules", t("common.modules")),
      numericColumn("estimate_points", t("workspace_analytics.projects.columns.estimates")),
      numericColumn(
        "estimated_time",
        t("workspace_analytics.time_tracking.allocated"),
        (row) => formatHours(row.estimated_time),
        (row) => row.estimated_time
      ),
      numericColumn(
        "time_logged",
        t("workspace_analytics.time_tracking.time_logged"),
        (row) => formatHours(row.time_logged),
        (row) => row.time_logged
      ),
      numericColumn(
        "utilization_percentage",
        t("workspace_analytics.time_tracking.utilization"),
        (row) => formatPercent(row.utilization_percentage),
        (row) => row.utilization_percentage ?? ""
      ),
    ];
  }, [getProjectById, t]);

  const peekProject = peekProjectId ? getProjectById(peekProjectId) : undefined;

  return (
    <AnalyticsSectionWrapper title={t("workspace_analytics.projects.breakdown")}>
      <InsightTable<"projects">
        analyticsType="projects"
        data={data}
        isLoading={isLoading}
        columns={columns}
        headerText={t("common.projects")}
        onExport={(rows) => data && exportCSV(rows, columns, workspaceSlug!.toString())}
      />
      <WorkItemsModal isOpen={!!peekProject} onClose={() => setPeekProjectId(null)} projectDetails={peekProject} />
    </AnalyticsSectionWrapper>
  );
});

export default ProjectsInsightTable;
