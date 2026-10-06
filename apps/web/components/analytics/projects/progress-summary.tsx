/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane package imports
import { ANALYTICS_PROGRESS_FIELDS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { IAnalyticsResponse, TAnalyticsGranularity } from "@plane/types";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
// services
import { AnalyticsService } from "@/services/analytics.service";
// local imports
import AnalyticsSectionWrapper from "../analytics-section-wrapper";
import InsightCard from "../insight-card";
import { GranularitySelect } from "../select/granularity";

const analyticsService = new AnalyticsService();
const PROGRESS_GRANULARITIES: TAnalyticsGranularity[] = ["day", "week"];

/** Daily / weekly team progress: the current period against the previous one. */
const ProgressSummary = observer(function ProgressSummary() {
  const { workspaceSlug } = useParams();
  const { t } = useTranslation();
  const { filterParams, filtersKey, isPeekView } = useAnalytics();
  const [granularity, setGranularity] = useState<TAnalyticsGranularity>("week");

  const { data, isLoading } = useSWR(
    workspaceSlug ? `analytics-progress-${workspaceSlug}-${filtersKey}-${granularity}` : null,
    () =>
      analyticsService.getAdvanceAnalytics<IAnalyticsResponse>(
        workspaceSlug!.toString(),
        "progress",
        { ...filterParams, granularity },
        isPeekView
      )
  );

  const isDaily = granularity === "day";

  return (
    <AnalyticsSectionWrapper
      title={t(isDaily ? "workspace_analytics.progress.daily_title" : "workspace_analytics.progress.weekly_title")}
      actions={<GranularitySelect value={granularity} onChange={setGranularity} allowed={PROGRESS_GRANULARITIES} />}
    >
      <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {ANALYTICS_PROGRESS_FIELDS.map((item) => (
          <InsightCard
            key={item.key}
            isLoading={isLoading}
            data={data?.[item.key]}
            label={t(item.i18nKey)}
            format={item.format}
            comparisonLabel={t(
              isDaily ? "workspace_analytics.progress.vs_yesterday" : "workspace_analytics.progress.vs_last_week"
            )}
          />
        ))}
      </div>
    </AnalyticsSectionWrapper>
  );
});

export default ProgressSummary;
