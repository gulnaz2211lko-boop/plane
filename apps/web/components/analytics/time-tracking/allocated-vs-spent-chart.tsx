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
import { formatBucketLabel } from "../format";
import { ChartLoader } from "../loaders";
import { GranularitySelect } from "../select/granularity";

const analyticsService = new AnalyticsService();

/** Hours allocated through time estimates vs. hours logged, per day / week / month. */
const AllocatedVsSpentChart = observer(function AllocatedVsSpentChart() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { filterParams, filtersKey, isPeekView, selectedGranularity, updateSelectedGranularity } = useAnalytics();

  const { data, isLoading } = useSWR(
    workspaceSlug ? `analytics-allocated-vs-spent-${workspaceSlug}-${filtersKey}-${selectedGranularity}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsCharts<IChartResponse>(
        workspaceSlug!.toString(),
        "allocated-vs-spent",
        { ...filterParams, granularity: selectedGranularity },
        isPeekView
      )
  );

  const parsedData = useMemo(
    () =>
      (data?.data ?? []).map((datum) =>
        Object.assign({}, datum, { name: formatBucketLabel(datum.key, selectedGranularity) })
      ),
    [data, selectedGranularity]
  );
  const hasData = (data?.data ?? []).some(
    (datum) => Number(datum.allocated_hours) > 0 || Number(datum.spent_hours) > 0
  );

  const bars: TBarItem<string>[] = useMemo(
    () => [
      {
        key: "allocated_hours",
        label: t("workspace_analytics.time_tracking.allocated_hours"),
        stackId: "allocated",
        fill: "#1192E8",
        textClassName: "",
        showTopBorderRadius: () => true,
        showBottomBorderRadius: () => true,
      },
      {
        key: "spent_hours",
        label: t("workspace_analytics.time_tracking.spent_hours"),
        stackId: "spent",
        fill: "#198038",
        textClassName: "",
        showTopBorderRadius: () => true,
        showBottomBorderRadius: () => true,
      },
    ],
    [t]
  );

  return (
    <AnalyticsSectionWrapper
      title={t("workspace_analytics.time_tracking.allocated_vs_spent")}
      actions={<GranularitySelect value={selectedGranularity} onChange={updateSelectedGranularity} />}
    >
      {isLoading ? (
        <ChartLoader />
      ) : hasData ? (
        <BarChart
          className="h-[370px] w-full"
          data={parsedData}
          bars={bars}
          barSize={selectedGranularity === "day" ? 8 : 20}
          margin={{ bottom: 30 }}
          xAxis={{ key: "name", label: t("date"), dy: 30 }}
          yAxis={{
            key: "count",
            label: t("workspace_analytics.time_tracking.hours"),
            allowDecimals: true,
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
          title={t("workspace_analytics.time_tracking.allocated_vs_spent_empty_state")}
        />
      )}
    </AnalyticsSectionWrapper>
  );
});

export default AllocatedVsSpentChart;
