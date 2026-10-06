/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import AnalyticsWrapper from "../analytics-wrapper";
import TotalInsights from "../total-insights";
import CreatedVsResolved from "../work-items/created-vs-resolved";
import ProgressSummary from "./progress-summary";
import ProjectDistribution from "./project-distribution";
import ProjectsInsightTable from "./projects-insight-table";

function ProjectsAnalytics() {
  return (
    <AnalyticsWrapper i18nTitle="common.projects">
      <div className="flex flex-col gap-14">
        <TotalInsights analyticsType="projects" />
        <ProgressSummary />
        <CreatedVsResolved />
        <ProjectDistribution />
        <ProjectsInsightTable />
      </div>
    </AnalyticsWrapper>
  );
}

export { ProjectsAnalytics };
