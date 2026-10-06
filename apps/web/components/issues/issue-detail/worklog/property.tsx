/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TIssueWorklog, TIssueWorklogPayload } from "@plane/types";
import { cn } from "@plane/utils";
// services
import { IssueWorklogService } from "@/services/issue";
// local imports
import { useWorklogDurationFormatter, getWorklogsSWRKey } from "./helper";
import { IssueWorklogModal } from "./modal";

const issueWorklogService = new IssueWorklogService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  /** Whether the current user may log new time on this work item. */
  disabled: boolean;
};

export const IssueWorklogProperty = observer(function IssueWorklogProperty(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled } = props;
  // states
  const [isModalOpen, setIsModalOpen] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  const formatWorklogDuration = useWorklogDurationFormatter();
  // fetching worklogs
  const { data: worklogs, mutate } = useSWR<TIssueWorklog[]>(
    workspaceSlug && projectId && issueId ? getWorklogsSWRKey(workspaceSlug, projectId, issueId) : null,
    () => issueWorklogService.list(workspaceSlug, projectId, issueId)
  );
  // derived values
  const totalDuration = (worklogs ?? []).reduce((total, worklog) => total + worklog.duration, 0);

  const handleCreate = async (payload: TIssueWorklogPayload) => {
    const worklog = await issueWorklogService.create(workspaceSlug, projectId, issueId, payload);
    await mutate((current) => [worklog, ...(current ?? [])], { revalidate: true });
  };

  const handleUpdate = async (worklogId: string, payload: TIssueWorklogPayload) => {
    const worklog = await issueWorklogService.update(workspaceSlug, projectId, issueId, worklogId, payload);
    await mutate((current) => (current ?? []).map((item) => (item.id === worklogId ? worklog : item)), {
      revalidate: true,
    });
  };

  const handleDelete = async (worklogId: string) => {
    await issueWorklogService.destroy(workspaceSlug, projectId, issueId, worklogId);
    await mutate((current) => (current ?? []).filter((item) => item.id !== worklogId), { revalidate: false });
  };

  return (
    <>
      <button
        type="button"
        className={cn(
          "flex h-7.5 w-full items-center rounded-sm px-2 text-left text-body-xs-regular hover:bg-layer-transparent-hover",
          totalDuration > 0 ? "text-primary" : "text-placeholder"
        )}
        onClick={() => setIsModalOpen(true)}
      >
        {totalDuration > 0
          ? formatWorklogDuration(totalDuration)
          : disabled
            ? t("work_item_worklog.no_time_logged")
            : t("work_item_worklog.log_time")}
      </button>
      <IssueWorklogModal
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        worklogs={worklogs ?? []}
        canLogTime={!disabled}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
      />
    </>
  );
});
