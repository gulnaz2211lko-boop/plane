/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import AnalyticsWrapper from "../analytics-wrapper";
import TotalInsights from "../total-insights";
import AllocatedVsSpentChart from "./allocated-vs-spent-chart";
import TeamspaceInsightTable from "./teamspace-insight-table";
import TimeLoggedChart from "./time-logged-chart";
import TimeTrackingInsightTable from "./time-tracking-insight-table";

function TimeTrackingAnalytics() {
  return (
    <AnalyticsWrapper i18nTitle="workspace_analytics.time_tracking.title">
      <div className="flex flex-col gap-14">
        <TotalInsights analyticsType="time-tracking" />
        <AllocatedVsSpentChart />
        <TimeLoggedChart />
        <TeamspaceInsightTable />
        <TimeTrackingInsightTable />
      </div>
    </AnalyticsWrapper>
  );
}

export { TimeTrackingAnalytics };
