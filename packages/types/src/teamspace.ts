/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TLogoProps } from "./common";

export type TTeamspace = {
  id: string;
  name: string;
  description: string;
  logo_props: TLogoProps;
  lead_id: string | null;
  member_ids: string[];
  project_ids: string[];
  workspace: string;
  created_at: string;
  updated_at: string;
};

export type TTeamspacePayload = Partial<
  Pick<TTeamspace, "name" | "description" | "logo_props" | "lead_id" | "member_ids" | "project_ids">
>;
