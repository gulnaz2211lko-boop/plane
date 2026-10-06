/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set, sortBy, unset } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// types
import type { TTeamspace, TTeamspacePayload } from "@plane/types";
// services
import { TeamspaceService } from "@/services/teamspace.service";
// store
import type { CoreRootStore } from "./root.store";

export interface ITeamspaceStore {
  // observables
  teamspaceMap: Record<string, TTeamspace>;
  fetchedMap: Record<string, boolean>;
  // computed actions
  getTeamspaceById: (teamspaceId: string) => TTeamspace | undefined;
  getWorkspaceTeamspaceIds: (workspaceSlug: string) => string[] | undefined;
  // actions
  fetchTeamspaces: (workspaceSlug: string) => Promise<TTeamspace[]>;
  createTeamspace: (workspaceSlug: string, data: TTeamspacePayload) => Promise<TTeamspace>;
  updateTeamspace: (workspaceSlug: string, teamspaceId: string, data: TTeamspacePayload) => Promise<TTeamspace>;
  deleteTeamspace: (workspaceSlug: string, teamspaceId: string) => Promise<void>;
}

export class TeamspaceStore implements ITeamspaceStore {
  // observables
  teamspaceMap: Record<string, TTeamspace> = {};
  fetchedMap: Record<string, boolean> = {};
  // root store
  rootStore;
  // services
  teamspaceService;

  constructor(_rootStore: CoreRootStore) {
    makeObservable(this, {
      // observables
      teamspaceMap: observable,
      fetchedMap: observable,
      // actions
      fetchTeamspaces: action,
      createTeamspace: action,
      updateTeamspace: action,
      deleteTeamspace: action,
    });
    this.rootStore = _rootStore;
    this.teamspaceService = new TeamspaceService();
  }

  getTeamspaceById = computedFn((teamspaceId: string) => this.teamspaceMap[teamspaceId]);

  /**
   * Returns the teamspace ids of a workspace sorted by name, undefined until fetched
   */
  getWorkspaceTeamspaceIds = computedFn((workspaceSlug: string) => {
    const workspaceDetails = this.rootStore.workspaceRoot.getWorkspaceBySlug(workspaceSlug);
    if (!workspaceDetails || !this.fetchedMap[workspaceSlug]) return undefined;
    return sortBy(
      Object.values(this.teamspaceMap).filter((teamspace) => teamspace.workspace === workspaceDetails.id),
      (teamspace) => teamspace.name.toLowerCase()
    ).map((teamspace) => teamspace.id);
  });

  fetchTeamspaces = async (workspaceSlug: string) => {
    const teamspaces = await this.teamspaceService.list(workspaceSlug);
    runInAction(() => {
      const workspaceId = this.rootStore.workspaceRoot.getWorkspaceBySlug(workspaceSlug)?.id;
      // drop stale entries of this workspace (e.g. deleted elsewhere) before re-hydrating
      Object.values(this.teamspaceMap).forEach((teamspace) => {
        if (teamspace.workspace === workspaceId) unset(this.teamspaceMap, [teamspace.id]);
      });
      teamspaces.forEach((teamspace) => set(this.teamspaceMap, [teamspace.id], teamspace));
      set(this.fetchedMap, [workspaceSlug], true);
    });
    return teamspaces;
  };

  createTeamspace = async (workspaceSlug: string, data: TTeamspacePayload) => {
    const teamspace = await this.teamspaceService.create(workspaceSlug, data);
    runInAction(() => {
      set(this.teamspaceMap, [teamspace.id], teamspace);
    });
    return teamspace;
  };

  updateTeamspace = async (workspaceSlug: string, teamspaceId: string, data: TTeamspacePayload) => {
    const teamspace = await this.teamspaceService.update(workspaceSlug, teamspaceId, data);
    runInAction(() => {
      set(this.teamspaceMap, [teamspace.id], teamspace);
    });
    return teamspace;
  };

  deleteTeamspace = async (workspaceSlug: string, teamspaceId: string) => {
    await this.teamspaceService.destroy(workspaceSlug, teamspaceId);
    runInAction(() => {
      unset(this.teamspaceMap, [teamspaceId]);
    });
  };
}
