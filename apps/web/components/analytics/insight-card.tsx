/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane package imports
import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { IInsightField } from "@plane/constants";
import type { IAnalyticsResponseFields } from "@plane/types";
import { Loader } from "@plane/blocks/skeleton";
import { cn } from "@plane/utils";
// local imports
import { formatInsightValue, getPeriodChange } from "./format";

export type InsightCardProps = {
  data?: IAnalyticsResponseFields;
  label: string;
  isLoading?: boolean;
  format?: IInsightField["format"];
  /** Label for the comparison period, shown when `data.previous_count` is present (e.g. "vs last week"). */
  comparisonLabel?: string;
};

function InsightCard(props: InsightCardProps) {
  const { data, label, isLoading = false, format, comparisonLabel } = props;
  const count = data?.count ?? 0;
  const previousCount = data?.previous_count;
  const change = getPeriodChange(count, previousCount);

  return (
    <div className="flex flex-col gap-3">
      <div className="text-13 text-tertiary">{label}</div>
      {!isLoading ? (
        <div className="flex flex-col gap-1">
          <div className="text-20 font-bold text-primary">{formatInsightValue(count, format)}</div>
          {previousCount !== undefined && (
            <div className="flex items-center gap-1 text-11 text-tertiary">
              {change !== null && (
                <span
                  className={cn(
                    "flex items-center gap-0.5 font-medium",
                    change >= 0 ? "text-success-primary" : "text-danger-primary"
                  )}
                >
                  {change >= 0 ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                  {Math.round(Math.abs(change))}%
                </span>
              )}
              <span>
                {comparisonLabel} ({formatInsightValue(previousCount, format)})
              </span>
            </div>
          )}
        </div>
      ) : (
        <Loader.Item height="50px" width="100%" />
      )}
    </div>
  );
}

export default InsightCard;
