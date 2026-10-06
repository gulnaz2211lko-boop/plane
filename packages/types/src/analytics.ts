/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TChartData } from "./charts";

export enum ChartXAxisProperty {
  STATES = "STATES",
  STATE_GROUPS = "STATE_GROUPS",
  LABELS = "LABELS",
  ASSIGNEES = "ASSIGNEES",
  ESTIMATE_POINTS = "ESTIMATE_POINTS",
  CYCLES = "CYCLES",
  MODULES = "MODULES",
  PRIORITY = "PRIORITY",
  START_DATE = "START_DATE",
  TARGET_DATE = "TARGET_DATE",
  CREATED_AT = "CREATED_AT",
  COMPLETED_AT = "COMPLETED_AT",
  CREATED_BY = "CREATED_BY",
  WORK_ITEM_TYPES = "WORK_ITEM_TYPES",
  PROJECTS = "PROJECTS",
  EPICS = "EPICS",
}

export enum ChartYAxisMetric {
  WORK_ITEM_COUNT = "WORK_ITEM_COUNT",
  ESTIMATE_POINT_COUNT = "ESTIMATE_POINT_COUNT",
  PENDING_WORK_ITEM_COUNT = "PENDING_WORK_ITEM_COUNT",
  COMPLETED_WORK_ITEM_COUNT = "COMPLETED_WORK_ITEM_COUNT",
  IN_PROGRESS_WORK_ITEM_COUNT = "IN_PROGRESS_WORK_ITEM_COUNT",
  WORK_ITEM_DUE_THIS_WEEK_COUNT = "WORK_ITEM_DUE_THIS_WEEK_COUNT",
  WORK_ITEM_DUE_TODAY_COUNT = "WORK_ITEM_DUE_TODAY_COUNT",
  BLOCKED_WORK_ITEM_COUNT = "BLOCKED_WORK_ITEM_COUNT",
  EPIC_WORK_ITEM_COUNT = "EPIC_WORK_ITEM_COUNT",
}

export type TAnalyticsTabsBase = "overview" | "work-items" | "projects" | "time-tracking";
/** Tabs served by `advance-analytics` that are not dashboard tabs of their own. */
export type TAnalyticsSummaryBase = TAnalyticsTabsBase | "progress";
export type TAnalyticsGraphsBase =
  | "projects"
  | "work-items"
  | "custom-work-items"
  | "project-distribution"
  | "time-logged"
  | "allocated-vs-spent";
/** Row-level breakdowns served by the advance-analytics-stats endpoint. */
export type TAnalyticsStatsBase = Exclude<TAnalyticsTabsBase, "overview"> | "teamspaces";
export type TAnalyticsGranularity = "day" | "week" | "month";
export interface AnalyticsTab {
  key: TAnalyticsTabsBase;
  label: string;
  content: React.FC;
  isDisabled: boolean;
}
export type TAnalyticsFilterParams = {
  project_ids?: string;
  teamspace_ids?: string;
  cycle_id?: string;
  module_id?: string;
  epic?: boolean;
  granularity?: TAnalyticsGranularity;
};

// service types

export interface IAnalyticsResponse {
  [key: string]: any;
}

export interface IAnalyticsResponseFields {
  count: number;
  filter_count?: number;
  /** Value for the previous period, returned by period-over-period summaries (tab=progress). */
  previous_count?: number;
}

// chart types

export interface IChartResponse {
  schema: Record<string, string>;
  data: TChartData<string, string>[];
}

// table types

export interface WorkItemInsightColumns {
  project_id?: string;
  project__name?: string;
  cancelled_work_items: number;
  completed_work_items: number;
  backlog_work_items: number;
  un_started_work_items: number;
  started_work_items: number;
  // in case of peek view, we will display the display_name instead of project__name
  display_name?: string;
  avatar_url?: string;
  assignee_id?: string;
}

export interface ProjectInsightColumns {
  project_id: string;
  project__name: string;
  total_work_items: number;
  completed_work_items: number;
  pending_work_items: number;
  cancelled_work_items: number;
  overdue_work_items: number;
  completion_percentage: number;
  total_members: number;
  total_cycles: number;
  total_modules: number;
  estimate_points: number | null;
  /** Hours allocated through time estimates */
  estimated_time: number;
  /** Hours */
  time_logged: number;
  /** Spent / allocated * 100; null when nothing is allocated */
  utilization_percentage: number | null;
  teamspace_ids: string[];
}

export interface TimeTrackingInsightColumns {
  project_id: string;
  project__name: string;
  member_id: string;
  display_name: string;
  avatar_url?: string | null;
  /** Hours */
  time_logged: number;
  /** Hours allocated to the member's assigned work items in the project */
  estimated_time: number;
  work_items_logged: number;
}

export interface TeamspaceInsightColumns {
  teamspace_id: string;
  name: string;
  total_projects: number;
  total_members: number;
  total_work_items: number;
  completed_work_items: number;
  pending_work_items: number;
  /** Hours allocated through time estimates */
  estimated_time: number;
  /** Hours */
  time_logged: number;
  /** Spent / allocated * 100; null when nothing is allocated */
  utilization_percentage: number | null;
}

export type AnalyticsTableDataMap = {
  "work-items": WorkItemInsightColumns;
  projects: ProjectInsightColumns;
  "time-tracking": TimeTrackingInsightColumns;
  teamspaces: TeamspaceInsightColumns;
};

export interface IAnalyticsParams {
  x_axis: ChartXAxisProperty;
  y_axis: ChartYAxisMetric;
  group_by?: ChartXAxisProperty;
}
