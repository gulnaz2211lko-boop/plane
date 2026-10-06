/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
// hooks
import { useDurationFormatter } from "@/hooks/use-duration-formatter";

export const getWorklogsSWRKey = (workspaceSlug: string, projectId: string, issueId: string) =>
  `ISSUE_WORKLOGS_${workspaceSlug}_${projectId}_${issueId}`;

/** Formatter for worklog durations in the current locale's units, e.g. "2h 30m"; "0m" for zero. */
export const useWorklogDurationFormatter = () => {
  const { t } = useTranslation();
  const formatDuration = useDurationFormatter();
  return useCallback(
    (totalMinutes: number) => formatDuration(totalMinutes) || t("common.duration_units.minutes", { count: 0 }),
    [formatDuration, t]
  );
};
