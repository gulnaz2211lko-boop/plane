/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useTheme } from "next-themes";
import useSWR from "swr";
// plane package imports
import { CHART_COLOR_PALETTES } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { BarChart } from "@plane/blocks/charts/bar-chart";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
import type { IChartResponse, TBarItem, TChartDatum } from "@plane/types";
// components
import { generateExtendedColors } from "@/components/chart/utils";
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

/** Hours logged per day / week / month, stacked by project. */
const TimeLoggedChart = observer(function TimeLoggedChart() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { filterParams, filtersKey, isPeekView, selectedGranularity, updateSelectedGranularity } = useAnalytics();

  const { data, isLoading } = useSWR(
    workspaceSlug ? `analytics-time-logged-${workspaceSlug}-${filtersKey}-${selectedGranularity}` : null,
    () =>
      analyticsService.getAdvanceAnalyticsCharts<IChartResponse>(
        workspaceSlug!.toString(),
        "time-logged",
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
  const hasLoggedTime = (data?.data ?? []).some((datum) => Number(datum.count) > 0);

  const bars: TBarItem<string>[] = useMemo(() => {
    const schemaKeys = Object.keys(data?.schema ?? {});
    const baseColors = CHART_COLOR_PALETTES[0]?.[resolvedTheme === "dark" ? "dark" : "light"];
    const colors = generateExtendedColors(baseColors ?? [], schemaKeys.length);
    // round only the outermost non-empty segment of each stack
    const isEdge = (edge: "top" | "bottom", key: string, payload: TChartDatum) => {
      const nonEmpty = schemaKeys.filter((schemaKey) => Number(payload[schemaKey]) > 0);
      return (edge === "top" ? nonEmpty[nonEmpty.length - 1] : nonEmpty[0]) === key;
    };
    return schemaKeys.map((key, index) => ({
      key,
      label: data?.schema[key] ?? key,
      stackId: "time-logged",
      fill: colors[index],
      textClassName: "",
      showTopBorderRadius: (barKey: string, payload: TChartDatum) => isEdge("top", barKey, payload),
      showBottomBorderRadius: (barKey: string, payload: TChartDatum) => isEdge("bottom", barKey, payload),
    }));
  }, [data, resolvedTheme]);

  return (
    <AnalyticsSectionWrapper
      title={t("workspace_analytics.time_tracking.time_logged_over_time")}
      actions={<GranularitySelect value={selectedGranularity} onChange={updateSelectedGranularity} />}
    >
      {isLoading ? (
        <ChartLoader />
      ) : hasLoggedTime ? (
        <BarChart
          className="h-[370px] w-full"
          data={parsedData}
          bars={bars}
          barSize={selectedGranularity === "day" ? 12 : 32}
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
          title={t("workspace_analytics.time_tracking.empty_state")}
        />
      )}
    </AnalyticsSectionWrapper>
  );
});

export default TimeLoggedChart;
