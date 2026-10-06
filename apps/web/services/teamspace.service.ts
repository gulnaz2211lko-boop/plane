/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TTeamspace, TTeamspacePayload } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

export class TeamspaceService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(workspaceSlug: string): Promise<TTeamspace[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/teamspaces/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async create(workspaceSlug: string, data: TTeamspacePayload): Promise<TTeamspace> {
    return this.post(`/api/workspaces/${workspaceSlug}/teamspaces/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(workspaceSlug: string, teamspaceId: string, data: TTeamspacePayload): Promise<TTeamspace> {
    return this.patch(`/api/workspaces/${workspaceSlug}/teamspaces/${teamspaceId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async destroy(workspaceSlug: string, teamspaceId: string): Promise<void> {
    return this.delete(`/api/workspaces/${workspaceSlug}/teamspaces/${teamspaceId}/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
