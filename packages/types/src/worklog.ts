/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TIssueWorklog = {
  id: string;
  issue_id: string;
  project_id: string;
  workspace_id: string;
  logged_by_id: string;
  /** duration in minutes */
  duration: number;
  /** YYYY-MM-DD */
  logged_at: string;
  description: string;
  created_at: string;
  updated_at: string;
};

export type TIssueWorklogPayload = Partial<Pick<TIssueWorklog, "duration" | "logged_at" | "description">>;
