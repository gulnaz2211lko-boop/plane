/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { convertMinutesToHoursMinutesString } from "@plane/utils";

export const getWorklogsSWRKey = (workspaceSlug: string, projectId: string, issueId: string) =>
  `ISSUE_WORKLOGS_${workspaceSlug}_${projectId}_${issueId}`;

/** Formats a duration in minutes as "Xh Ym" ("0m" for zero). */
export const formatWorklogDuration = (totalMinutes: number) =>
  convertMinutesToHoursMinutesString(totalMinutes).trim() || "0m";
