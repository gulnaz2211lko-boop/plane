/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { action, computed, makeObservable, observable, runInAction } from "mobx";
import { ANALYTICS_DURATION_FILTER_OPTIONS } from "@plane/constants";
import type { TAnalyticsFilterParams, TAnalyticsGranularity, TAnalyticsTabsBase } from "@plane/types";

type DurationType = (typeof ANALYTICS_DURATION_FILTER_OPTIONS)[number]["value"];

export interface IBaseAnalyticsStore {
  //observables
  currentTab: TAnalyticsTabsBase;
  selectedProjects: string[];
  selectedTeamspaces: string[];
  selectedGranularity: TAnalyticsGranularity;
  selectedDuration: DurationType;
  selectedCycle: string;
  selectedModule: string;
  isPeekView?: boolean;
  isEpic?: boolean;
  //computed
  selectedDurationLabel: DurationType | null;
  /** Query params shared by every analytics request (projects, teamspaces, cycle, module, epic). */
  filterParams: TAnalyticsFilterParams;
  /** Stable cache-key fragment for `filterParams`, for use in SWR keys. */
  filtersKey: string;

  //actions
  updateSelectedProjects: (projects: string[]) => void;
  updateSelectedTeamspaces: (teamspaces: string[]) => void;
  updateSelectedGranularity: (granularity: TAnalyticsGranularity) => void;
  updateSelectedDuration: (duration: DurationType) => void;
  updateSelectedCycle: (cycle: string) => void;
  updateSelectedModule: (module: string) => void;
  updateIsPeekView: (isPeekView: boolean) => void;
  updateIsEpic: (isEpic: boolean) => void;
}

export class BaseAnalyticsStore implements IBaseAnalyticsStore {
  //observables
  currentTab: TAnalyticsTabsBase = "overview";
  selectedProjects: string[] = [];
  selectedTeamspaces: string[] = [];
  selectedGranularity: TAnalyticsGranularity = "week";
  selectedDuration: DurationType = "last_30_days";
  selectedCycle: string = "";
  selectedModule: string = "";
  isPeekView: boolean = false;
  isEpic: boolean = false;
  constructor() {
    makeObservable(this, {
      // observables
      currentTab: observable.ref,
      selectedDuration: observable.ref,
      selectedProjects: observable,
      selectedTeamspaces: observable,
      selectedGranularity: observable.ref,
      selectedCycle: observable.ref,
      selectedModule: observable.ref,
      isPeekView: observable.ref,
      isEpic: observable.ref,
      // computed
      selectedDurationLabel: computed,
      filterParams: computed,
      filtersKey: computed,
      // actions
      updateSelectedProjects: action,
      updateSelectedTeamspaces: action,
      updateSelectedGranularity: action,
      updateSelectedDuration: action,
      updateSelectedCycle: action,
      updateSelectedModule: action,
      updateIsPeekView: action,
      updateIsEpic: action,
    });
  }

  get selectedDurationLabel() {
    return ANALYTICS_DURATION_FILTER_OPTIONS.find((item) => item.value === this.selectedDuration)?.name ?? null;
  }

  get filterParams(): TAnalyticsFilterParams {
    return {
      ...(this.selectedProjects.length > 0 ? { project_ids: this.selectedProjects.join(",") } : {}),
      // the peek view is pinned to a single project, so the workspace-level teamspace filter does not apply
      ...(!this.isPeekView && this.selectedTeamspaces.length > 0
        ? { teamspace_ids: this.selectedTeamspaces.join(",") }
        : {}),
      ...(this.selectedCycle ? { cycle_id: this.selectedCycle } : {}),
      ...(this.selectedModule ? { module_id: this.selectedModule } : {}),
      ...(this.isEpic ? { epic: true } : {}),
    };
  }

  get filtersKey() {
    const { project_ids, teamspace_ids, cycle_id, module_id, epic } = this.filterParams;
    return [project_ids, teamspace_ids, cycle_id, module_id, epic, this.isPeekView].map((v) => v ?? "").join("|");
  }

  updateSelectedTeamspaces = (teamspaces: string[]) => {
    runInAction(() => {
      this.selectedTeamspaces = teamspaces;
    });
  };

  updateSelectedGranularity = (granularity: TAnalyticsGranularity) => {
    runInAction(() => {
      this.selectedGranularity = granularity;
    });
  };

  updateSelectedProjects = (projects: string[]) => {
    try {
      runInAction(() => {
        this.selectedProjects = projects;
      });
    } catch (error) {
      console.error("Failed to update selected project");
      throw error;
    }
  };

  updateSelectedDuration = (duration: DurationType) => {
    try {
      runInAction(() => {
        this.selectedDuration = duration;
      });
    } catch (error) {
      console.error("Failed to update selected duration");
      throw error;
    }
  };

  updateSelectedCycle = (cycle: string) => {
    runInAction(() => {
      this.selectedCycle = cycle;
    });
  };

  updateSelectedModule = (module: string) => {
    runInAction(() => {
      this.selectedModule = module;
    });
  };

  updateIsPeekView = (isPeekView: boolean) => {
    runInAction(() => {
      this.isPeekView = isPeekView;
    });
  };

  updateIsEpic = (isEpic: boolean) => {
    runInAction(() => {
      this.isEpic = isEpic;
    });
  };
}
