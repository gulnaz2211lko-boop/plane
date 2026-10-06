/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInsightField } from "@plane/constants";
import type { TAnalyticsGranularity } from "@plane/types";
import { renderFormattedDate } from "@plane/utils";

type TTranslate = (key: string, params?: Record<string, unknown>) => string;

/** Renders an hours value from the analytics API through the locale's unit, e.g. `12.5 h`, `0 h`. */
export const formatHours = (hours: number | null | undefined, t: TTranslate): string => {
  const value = Math.round((hours ?? 0) * 10) / 10;
  return t("workspace_analytics.hours_value", { value: value.toLocaleString() });
};

/** Renders a percentage from the analytics API, e.g. `82.5%`; `—` when there is no value (nothing to compare). */
export const formatPercent = (value: number | null | undefined): string =>
  value === null || value === undefined ? "—" : `${(Math.round(value * 10) / 10).toLocaleString()}%`;

export const formatInsightValue = (
  value: number | null | undefined,
  t: TTranslate,
  format: IInsightField["format"] = "count"
) => {
  if (format === "hours") return formatHours(value, t);
  if (format === "percent") return formatPercent(value ?? 0);
  return (value ?? 0).toLocaleString();
};

/** Percentage change from `previous` to `current`; null when there is no baseline to compare with. */
export const getPeriodChange = (current: number, previous: number | undefined): number | null => {
  if (previous === undefined || previous === 0) return null;
  return ((current - previous) / previous) * 100;
};

/** Axis label for a time-series bucket key (`YYYY-MM-DD`): `MMM yyyy` for months, the date otherwise. */
export const formatBucketLabel = (key: string, granularity: TAnalyticsGranularity): string =>
  (granularity === "month" ? renderFormattedDate(key, "MMM yyyy") : renderFormattedDate(key)) ?? key;
