/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane package imports
import { useTranslation } from "@plane/i18n";
import { BarChart } from "@plane/blocks/charts/bar-chart";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
import type { IChartResponse, TBarItem } from "@plane/types";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local imports
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import { ChartLoader } from "../loaders";

const analyticsService = new AnalyticsService();

/** Work item distribution across projects: completed + pending stacked, overdue alongside. */
const ProjectDistribution = observer(function ProjectDistribution() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { filterParams, filtersKey, isPeekView } = useAnalytics();

  const { data, isLoading } = useSWR(
    workspaceSlug ? `analytics-project-distribution-${workspaceSlug}-${filtersKey}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsCharts<IChartResponse>(
        workspaceSlug!.toString(),
        "project-distribution",
        filterParams,
        isPeekView
      )
  );

  const bars: TBarItem<string>[] = useMemo(
    () => [
      {
        key: "completed_work_items",
        label: t("workspace_projects.state.completed"),
        stackId: "progress",
        fill: "#198038",
        textClassName: "",
        showTopBorderRadius: (_key, payload) => !payload.pending_work_items,
        showBottomBorderRadius: () => true,
      },
      {
        key: "pending_work_items",
        label: t("workspace_analytics.projects.pending"),
        stackId: "progress",
        fill: "#1192E8",
        textClassName: "",
        showTopBorderRadius: () => true,
        showBottomBorderRadius: (_key, payload) => !payload.completed_work_items,
      },
      {
        key: "overdue_work_items",
        label: t("workspace_analytics.projects.overdue"),
        stackId: "overdue",
        fill: "#DA1E28",
        textClassName: "",
        showTopBorderRadius: () => true,
        showBottomBorderRadius: () => true,
      },
    ],
    [t]
  );

  return (
    <AnalyticsSectionWrapper title={t("workspace_analytics.projects.distribution")}>
      {isLoading ? (
        <ChartLoader />
      ) : data?.data && data.data.length > 0 ? (
        <BarChart
          className="h-[370px] w-full"
          data={data.data}
          bars={bars}
          barSize={24}
          margin={{ bottom: 30 }}
          xAxis={{ key: "name", label: t("common.project"), dy: 30 }}
          yAxis={{
            key: "count",
            label: t("common.no_of", { entity: t("work_items") }),
            offset: -60,
            dx: -26,
          }}
          legend={{
            align: "left",
            verticalAlign: "bottom",
            layout: "horizontal",
            wrapperStyles: { paddingTop: "40px" },
          }}
        />
      ) : (
        <EmptyStateCompact
          assetKey="unknown"
          assetClassName="size-20"
          rootClassName="border border-subtle px-5 py-10 md:py-20 md:px-20"
          title={t("workspace_empty_state.analytics_work_items.title")}
        />
      )}
    </AnalyticsSectionWrapper>
  );
});

export default ProjectDistribution;
