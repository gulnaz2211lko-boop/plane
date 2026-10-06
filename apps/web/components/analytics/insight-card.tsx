/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane package imports
import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { IInsightField } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
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
  const { t } = useTranslation();
  const count = data?.count ?? 0;
  const previousCount = data?.previous_count;
  const change = getPeriodChange(count, previousCount);
  // A change that rounds to 0% is shown as neutral rather than as growth.
  const roundedChange = change === null ? null : Math.round(change);

  return (
    <div className="flex flex-col gap-3">
      <div className="text-13 text-tertiary">{label}</div>
      {!isLoading ? (
        <div className="flex flex-col gap-1">
          <div className="text-20 font-bold text-primary">{formatInsightValue(count, t, format)}</div>
          {previousCount !== undefined && (
            <div className="flex items-center gap-1 text-11 text-tertiary">
              {roundedChange !== null && (
                <span
                  className={cn(
                    "flex items-center gap-0.5 font-medium",
                    roundedChange > 0 && "text-success-primary",
                    roundedChange < 0 && "text-danger-primary"
                  )}
                >
                  {roundedChange > 0 && <TrendingUp className="size-3" />}
                  {roundedChange < 0 && <TrendingDown className="size-3" />}
                  {Math.abs(roundedChange)}%
                </span>
              )}
              <span>
                {comparisonLabel} ({formatInsightValue(previousCount, t, format)})
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
