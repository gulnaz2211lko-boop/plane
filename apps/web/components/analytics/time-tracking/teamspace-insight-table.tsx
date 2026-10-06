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
import { MembersOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TeamspaceInsightColumns } from "@plane/types";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
import { useTeamspace } from "@/hooks/store/use-teamspace";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local imports
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import { exportCSV } from "../export";
import { formatHours, formatPercent } from "../format";
import { InsightTable } from "../insight-table";

const analyticsService = new AnalyticsService();

type TNumericColumn = Exclude<keyof TeamspaceInsightColumns, "teamspace_id" | "name">;

/** How work and time (allocated vs. spent) are distributed across teamspaces. */
const TeamspaceInsightTable = observer(function TeamspaceInsightTable() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  // store hooks
  const { filterParams, filtersKey, isPeekView } = useAnalytics();
  const { getTeamspaceById, getWorkspaceTeamspaceIds } = useTeamspace();
  // derived values
  const workspaceTeamspaceIds = workspaceSlug ? getWorkspaceTeamspaceIds(workspaceSlug.toString()) : undefined;
  const hasTeamspaces = !!workspaceTeamspaceIds && workspaceTeamspaceIds.length > 0;

  const { data, isLoading } = useSWR(
    workspaceSlug && hasTeamspaces && !isPeekView ? `insights-table-teamspaces-${workspaceSlug}-${filtersKey}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsStats<TeamspaceInsightColumns[]>(
        workspaceSlug!.toString(),
        "teamspaces",
        filterParams
      )
  );

  const columns: ColumnDef<TeamspaceInsightColumns>[] = useMemo(() => {
    const numericColumn = (
      key: TNumericColumn,
      label: string,
      render: (row: TeamspaceInsightColumns) => React.ReactNode = (row) => row[key] ?? "-",
      exportValue: (row: TeamspaceInsightColumns) => string | number = (row) => row[key] ?? ""
    ): ColumnDef<TeamspaceInsightColumns> => ({
      accessorKey: key,
      header: () => <div className="text-right">{label}</div>,
      cell: ({ row }) => <div className="text-right">{render(row.original)}</div>,
      meta: { export: { key: label, value: (row) => exportValue(row.original) } },
    });

    return [
      {
        accessorKey: "name",
        header: () => <div className="text-left">{t("workspace_analytics.time_tracking.teamspace")}</div>,
        cell: ({ row }) => {
          const teamspace = getTeamspaceById(row.original.teamspace_id);
          return (
            <div className="flex items-center gap-2">
              {teamspace?.logo_props?.in_use ? (
                <Logo logo={teamspace.logo_props} size={18} />
              ) : (
                <MembersOutline className="h-4 w-4" />
              )}
              {teamspace?.name ?? row.original.name}
            </div>
          );
        },
        meta: {
          export: { key: t("workspace_analytics.time_tracking.teamspace"), value: (row) => row.original.name },
        },
      },
      numericColumn("total_projects", t("workspace_analytics.time_tracking.projects")),
      numericColumn("total_members", t("workspace_analytics.time_tracking.members")),
      numericColumn("total_work_items", t("workspace_analytics.time_tracking.work_items")),
      numericColumn("completed_work_items", t("workspace_analytics.time_tracking.completed")),
      numericColumn("pending_work_items", t("workspace_analytics.time_tracking.pending")),
      numericColumn(
        "estimated_time",
        t("workspace_analytics.time_tracking.allocated"),
        (row) => formatHours(row.estimated_time, t),
        (row) => row.estimated_time
      ),
      numericColumn(
        "time_logged",
        t("workspace_analytics.time_tracking.time_logged"),
        (row) => formatHours(row.time_logged, t),
        (row) => row.time_logged
      ),
      numericColumn(
        "utilization_percentage",
        t("workspace_analytics.time_tracking.utilization"),
        (row) => formatPercent(row.utilization_percentage),
        (row) => row.utilization_percentage ?? ""
      ),
    ];
  }, [getTeamspaceById, t]);

  // teamspaces are a workspace-level grouping; nothing to show without any, or inside a single-project peek
  if (!hasTeamspaces || isPeekView) return null;

  return (
    <AnalyticsSectionWrapper title={t("workspace_analytics.time_tracking.by_teamspace")}>
      <InsightTable<"teamspaces">
        analyticsType="teamspaces"
        data={data}
        isLoading={isLoading}
        columns={columns}
        headerText={t("workspace_analytics.time_tracking.teamspaces")}
        onExport={(rows) => data && exportCSV(rows, columns, workspaceSlug!.toString())}
      />
    </AnalyticsSectionWrapper>
  );
});

export default TeamspaceInsightTable;
