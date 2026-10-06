/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { EstimateOutline } from "@makeplane/propel/icons";
import { EEstimateSystem } from "@plane/types";
import { cn } from "@plane/utils";
// hooks
import { useProjectEstimates } from "@/hooks/store/estimates";
import { useEstimate } from "@/hooks/store/estimates/use-estimate";
import { useDurationFormatter } from "@/hooks/use-duration-formatter";

export type TReadonlyEstimateProps = {
  className?: string;
  hideIcon?: boolean;
  value: string | undefined | null;
  placeholder?: string;
  projectId: string | undefined;
  workspaceSlug: string;
};

export const ReadonlyEstimate = observer(function ReadonlyEstimate(props: TReadonlyEstimateProps) {
  const { className, hideIcon = false, value, placeholder, projectId, workspaceSlug } = props;

  const { t } = useTranslation();
  const formatDuration = useDurationFormatter();
  const { currentActiveEstimateIdByProjectId, getEstimateById, getProjectEstimates } = useProjectEstimates();

  const currentActiveEstimateId = projectId ? currentActiveEstimateIdByProjectId(projectId) : undefined;
  const currentActiveEstimate = currentActiveEstimateId ? getEstimateById(currentActiveEstimateId) : undefined;
  const { estimatePointById } = useEstimate(currentActiveEstimateId);

  const estimatePoint = value ? estimatePointById(value) : null;

  const displayValue = estimatePoint
    ? currentActiveEstimate?.type === EEstimateSystem.TIME
      ? formatDuration(Number(estimatePoint.value))
      : estimatePoint.value
    : null;

  useEffect(() => {
    if (projectId) {
      getProjectEstimates(workspaceSlug, projectId);
    }
    // oxlint-disable-next-line react-hooks/exhaustive-deps -- store action; refetch only when the project changes
  }, [projectId, workspaceSlug]);

  return (
    <div className={cn("flex items-center gap-1 text-body-xs-regular", className)}>
      {!hideIcon && <EstimateOutline className="size-4 flex-shrink-0" />}
      <span className="flex-grow truncate">{displayValue ?? placeholder ?? t("common.none")}</span>
    </div>
  );
});
