/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TAnalyticsGranularity, TAnalyticsTabsBase } from "@plane/types";
import { ChartXAxisProperty, ChartYAxisMetric } from "@plane/types";

export interface IInsightField {
  key: string;
  i18nKey: string;
  /** How the value is rendered; defaults to a plain count. */
  format?: "count" | "hours" | "percent";
  i18nProps?: {
    entity?: string;
    entityPlural?: string;
    prefix?: string;
    suffix?: string;
    [key: string]: unknown;
  };
}

export const ANALYTICS_INSIGHTS_FIELDS: Record<TAnalyticsTabsBase, IInsightField[]> = {
  overview: [
    {
      key: "total_users",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.users",
      },
    },
    {
      key: "total_admins",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.admins",
      },
    },
    {
      key: "total_members",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.members",
      },
    },
    {
      key: "total_guests",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.guests",
      },
    },
    {
      key: "total_projects",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.projects",
      },
    },
    {
      key: "total_work_items",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.work_items",
      },
    },
    {
      key: "total_cycles",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "common.cycles",
      },
    },
    {
      key: "total_intake",
      i18nKey: "workspace_analytics.total",
      i18nProps: {
        entity: "sidebar.intake",
      },
    },
  ],
  "work-items": [
    {
      key: "total_work_items",
      i18nKey: "workspace_analytics.total",
    },
    {
      key: "started_work_items",
      i18nKey: "workspace_analytics.started_work_items",
    },
    {
      key: "backlog_work_items",
      i18nKey: "workspace_analytics.backlog_work_items",
    },
    {
      key: "un_started_work_items",
      i18nKey: "workspace_analytics.un_started_work_items",
    },
    {
      key: "completed_work_items",
      i18nKey: "workspace_analytics.completed_work_items",
    },
  ],
  projects: [
    {
      key: "total_projects",
      i18nKey: "workspace_analytics.total",
      i18nProps: { entity: "common.projects" },
    },
    {
      key: "total_work_items",
      i18nKey: "workspace_analytics.total",
      i18nProps: { entity: "common.work_items" },
    },
    {
      key: "completed_work_items",
      i18nKey: "workspace_analytics.completed_work_items",
      i18nProps: { entity: "common.work_items" },
    },
    {
      key: "overdue_work_items",
      i18nKey: "workspace_analytics.overdue_work_items",
      i18nProps: { entity: "common.work_items" },
    },
    {
      key: "total_members",
      i18nKey: "workspace_analytics.total",
      i18nProps: { entity: "common.members" },
    },
    {
      key: "total_time_logged",
      i18nKey: "workspace_analytics.time_tracking.total_time_logged",
      format: "hours",
    },
  ],
  "time-tracking": [
    {
      key: "total_time_logged",
      i18nKey: "workspace_analytics.time_tracking.total_time_logged",
      format: "hours",
    },
    {
      key: "time_logged_this_week",
      i18nKey: "workspace_analytics.time_tracking.time_logged_this_week",
      format: "hours",
    },
    {
      key: "time_logged_last_week",
      i18nKey: "workspace_analytics.time_tracking.time_logged_last_week",
      format: "hours",
    },
    {
      key: "total_estimated_time",
      i18nKey: "workspace_analytics.time_tracking.total_estimated_time",
      format: "hours",
    },
    {
      key: "utilization_percentage",
      i18nKey: "workspace_analytics.time_tracking.utilization_percentage",
      format: "percent",
    },
    {
      key: "contributors",
      i18nKey: "workspace_analytics.time_tracking.contributors",
    },
  ],
};

/** Period-over-period summary cards (`advance-analytics?tab=progress`). */
export const ANALYTICS_PROGRESS_FIELDS: IInsightField[] = [
  { key: "created_work_items", i18nKey: "workspace_analytics.progress.created_work_items" },
  { key: "completed_work_items", i18nKey: "workspace_analytics.progress.completed_work_items" },
  { key: "time_logged", i18nKey: "workspace_analytics.progress.time_logged", format: "hours" },
  { key: "active_contributors", i18nKey: "workspace_analytics.progress.active_contributors" },
];

export const ANALYTICS_GRANULARITY_OPTIONS: { value: TAnalyticsGranularity; i18nKey: string }[] = [
  { value: "day", i18nKey: "workspace_analytics.granularity.day" },
  { value: "week", i18nKey: "workspace_analytics.granularity.week" },
  { value: "month", i18nKey: "workspace_analytics.granularity.month" },
];

export const ANALYTICS_DURATION_FILTER_OPTIONS = [
  {
    name: "Yesterday",
    value: "yesterday",
  },
  {
    name: "Last 7 days",
    value: "last_7_days",
  },
  {
    name: "Last 30 days",
    value: "last_30_days",
  },
  {
    name: "Last 3 months",
    value: "last_3_months",
  },
];

export const ANALYTICS_X_AXIS_VALUES: { value: ChartXAxisProperty; label: string }[] = [
  {
    value: ChartXAxisProperty.STATES,
    label: "State name",
  },
  {
    value: ChartXAxisProperty.STATE_GROUPS,
    label: "State group",
  },
  {
    value: ChartXAxisProperty.PRIORITY,
    label: "Priority",
  },
  {
    value: ChartXAxisProperty.LABELS,
    label: "Label",
  },
  {
    value: ChartXAxisProperty.ASSIGNEES,
    label: "Assignee",
  },
  {
    value: ChartXAxisProperty.PROJECTS,
    label: "Project",
  },
  {
    value: ChartXAxisProperty.ESTIMATE_POINTS,
    label: "Estimate point",
  },
  {
    value: ChartXAxisProperty.CYCLES,
    label: "Cycle",
  },
  {
    value: ChartXAxisProperty.MODULES,
    label: "Module",
  },
  {
    value: ChartXAxisProperty.COMPLETED_AT,
    label: "Completed date",
  },
  {
    value: ChartXAxisProperty.TARGET_DATE,
    label: "Due date",
  },
  {
    value: ChartXAxisProperty.START_DATE,
    label: "Start date",
  },
  {
    value: ChartXAxisProperty.CREATED_AT,
    label: "Created date",
  },
];

export const ANALYTICS_Y_AXIS_VALUES: { value: ChartYAxisMetric; label: string }[] = [
  {
    value: ChartYAxisMetric.WORK_ITEM_COUNT,
    label: "Work item",
  },
  {
    value: ChartYAxisMetric.ESTIMATE_POINT_COUNT,
    label: "Estimate",
  },
  {
    value: ChartYAxisMetric.EPIC_WORK_ITEM_COUNT,
    label: "Epic",
  },
];

export const ANALYTICS_V2_DATE_KEYS = ["completed_at", "target_date", "start_date", "created_at"];
