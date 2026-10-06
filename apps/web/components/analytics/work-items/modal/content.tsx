/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
// plane package imports
import type { ICycle, IModule, IProject } from "@plane/types";
import { Spinner } from "@plane/blocks/spinner";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
// plane web components
import TotalInsights from "../../total-insights";
import CreatedVsResolved from "../created-vs-resolved";
import CustomizedInsights from "../customized-insights";
import WorkItemsInsightTable from "../workitems-insight-table";

type Props = {
  fullScreen: boolean;
  projectDetails: IProject | undefined;
  cycleDetails: ICycle | undefined;
  moduleDetails: IModule | undefined;
  isEpic?: boolean;
};

export const WorkItemsModalMainContent = observer(function WorkItemsModalMainContent(props: Props) {
  const { projectDetails, cycleDetails, moduleDetails, fullScreen, isEpic } = props;
  const {
    selectedProjects,
    selectedCycle,
    selectedModule,
    updateSelectedProjects,
    updateSelectedCycle,
    updateSelectedModule,
    updateIsPeekView,
  } = useAnalytics();
  const [isModalConfigured, setIsModalConfigured] = useState(false);
  // filters active before the peek view opened (e.g. on the analytics dashboard), restored on close
  const previousFiltersRef = useRef({ projects: [...selectedProjects], cycle: selectedCycle, module: selectedModule });

  useEffect(() => {
    const previousFilters = previousFiltersRef.current;
    updateIsPeekView(true);

    // Handle project selection
    if (projectDetails?.id) {
      updateSelectedProjects([projectDetails.id]);
    }

    // Handle cycle selection
    if (cycleDetails?.id) {
      updateSelectedCycle(cycleDetails.id);
    }

    // Handle module selection
    if (moduleDetails?.id) {
      updateSelectedModule(moduleDetails.id);
    }
    setIsModalConfigured(true);

    // Cleanup fields
    return () => {
      updateSelectedProjects(previousFilters.projects);
      updateSelectedCycle(previousFilters.cycle);
      updateSelectedModule(previousFilters.module);
      updateIsPeekView(false);
    };
  }, [
    projectDetails?.id,
    cycleDetails?.id,
    moduleDetails?.id,
    updateSelectedProjects,
    updateSelectedCycle,
    updateSelectedModule,
    updateIsPeekView,
  ]);

  if (!isModalConfigured)
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );

  return (
    <div className="flex flex-col gap-14 overflow-y-auto p-6">
      <TotalInsights analyticsType="work-items" peekView={!fullScreen} />
      <CreatedVsResolved />
      <CustomizedInsights peekView={!fullScreen} isEpic={isEpic} />
      <WorkItemsInsightTable />
    </div>
  );
});
