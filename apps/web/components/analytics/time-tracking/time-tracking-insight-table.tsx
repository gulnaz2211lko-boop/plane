/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane package imports
import { Avatar } from "@makeplane/propel/components/avatar";
import { ProjectsOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TimeTrackingInsightColumns } from "@plane/types";
import { getFileURL } from "@plane/utils";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
import { useProject } from "@/hooks/store/use-project";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local imports
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import { exportCSV } from "../export";
import { formatHours } from "../format";
import { InsightTable } from "../insight-table";

const analyticsService = new AnalyticsService();

const TimeTrackingInsightTable = observer(function TimeTrackingInsightTable() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { getProjectById } = useProject();
  const { filterParams, filtersKey, isPeekView } = useAnalytics();

  const { data, isLoading } = useSWR(
    workspaceSlug ? `insights-table-time-tracking-${workspaceSlug}-${filtersKey}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsStats<TimeTrackingInsightColumns[]>(
        workspaceSlug!.toString(),
        "time-tracking",
        filterParams,
        isPeekView
      )
  );

  const columns: ColumnDef<TimeTrackingInsightColumns>[] = useMemo(
    () => [
      {
        accessorKey: "display_name",
        header: () => <div className="text-left">{t("common.member")}</div>,
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <Avatar
              alt={row.original.display_name}
              fallback={row.original.display_name?.[0]?.toUpperCase()}
              src={row.original.avatar_url ? getFileURL(row.original.avatar_url) : undefined}
              size="sm"
            />
            <span className="break-words text-secondary">{row.original.display_name}</span>
          </div>
        ),
        meta: { export: { key: t("common.member"), value: (row) => row.original.display_name } },
      },
      {
        accessorKey: "project__name",
        header: () => <div className="text-left">{t("common.project")}</div>,
        cell: ({ row }) => {
          const project = getProjectById(row.original.project_id);
          return (
            <div className="flex items-center gap-2">
              {project?.logo_props ? (
                <Logo logo={project.logo_props} size={18} />
              ) : (
                <ProjectsOutline className="h-4 w-4" />
              )}
              {project?.name ?? row.original.project__name}
            </div>
          );
        },
        meta: { export: { key: t("common.project"), value: (row) => row.original.project__name } },
      },
      {
        accessorKey: "work_items_logged",
        header: () => <div className="text-right">{t("workspace_analytics.time_tracking.work_items_logged")}</div>,
        cell: ({ row }) => <div className="text-right">{row.original.work_items_logged}</div>,
        meta: {
          export: {
            key: t("workspace_analytics.time_tracking.work_items_logged"),
            value: (row) => row.original.work_items_logged,
          },
        },
      },
      {
        accessorKey: "estimated_time",
        header: () => <div className="text-right">{t("workspace_analytics.time_tracking.allocated")}</div>,
        cell: ({ row }) => <div className="text-right">{formatHours(row.original.estimated_time, t)}</div>,
        meta: {
          export: {
            key: t("workspace_analytics.time_tracking.allocated"),
            value: (row) => row.original.estimated_time,
          },
        },
      },
      {
        accessorKey: "time_logged",
        header: () => <div className="text-right">{t("workspace_analytics.time_tracking.time_logged")}</div>,
        cell: ({ row }) => <div className="text-right">{formatHours(row.original.time_logged, t)}</div>,
        meta: {
          export: {
            key: t("workspace_analytics.time_tracking.time_logged_hours"),
            value: (row) => row.original.time_logged,
          },
        },
      },
    ],
    [getProjectById, t]
  );

  return (
    <AnalyticsSectionWrapper title={t("workspace_analytics.time_tracking.by_member")}>
      <InsightTable<"time-tracking">
        analyticsType="time-tracking"
        data={data}
        isLoading={isLoading}
        columns={columns}
        headerText={t("common.members")}
        onExport={(rows) => data && exportCSV(rows, columns, workspaceSlug!.toString())}
      />
    </AnalyticsSectionWrapper>
  );
});

export default TimeTrackingInsightTable;
