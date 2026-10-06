/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Avatar } from "@makeplane/propel/components/avatar";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { DeleteOutline, EditOutline } from "@makeplane/propel/icons";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TIssueWorklog, TIssueWorklogPayload } from "@plane/types";
import { getFileURL, renderFormattedDate } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useUser, useUserPermissions } from "@/hooks/store/user";
// local imports
import { IssueWorklogForm } from "./form";
import { useWorklogDurationFormatter } from "./helper";

type Props = {
  workspaceSlug: string;
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  worklogs: TIssueWorklog[];
  /** Whether the current user may log new time (project admin/member on an editable work item). */
  canLogTime: boolean;
  onCreate: (payload: TIssueWorklogPayload) => Promise<void>;
  onUpdate: (worklogId: string, payload: TIssueWorklogPayload) => Promise<void>;
  onDelete: (worklogId: string) => Promise<void>;
};

const getErrorMessage = (err: unknown, fallback: string) =>
  err && typeof err === "object" && "error" in err && typeof err.error === "string" && err.error ? err.error : fallback;

export const IssueWorklogModal = observer(function IssueWorklogModal(props: Props) {
  const { workspaceSlug, projectId, isOpen, onClose, worklogs, canLogTime, onCreate, onUpdate, onDelete } = props;
  // states
  const [editingWorklogId, setEditingWorklogId] = useState<string | undefined>(undefined);
  const [deletingWorklogId, setDeletingWorklogId] = useState<string | undefined>(undefined);
  const [isDeleting, setIsDeleting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  const formatWorklogDuration = useWorklogDurationFormatter();
  // store hooks
  const { data: currentUser } = useUser();
  const { getUserDetails } = useMember();
  const { allowPermissions } = useUserPermissions();
  // derived values
  const isProjectAdmin = allowPermissions(
    [EUserPermissions.ADMIN],
    EUserPermissionsLevel.PROJECT,
    workspaceSlug,
    projectId
  );
  const totalDuration = worklogs.reduce((total, worklog) => total + worklog.duration, 0);
  const editingWorklog = worklogs.find((worklog) => worklog.id === editingWorklogId);

  const withToast = async (action: () => Promise<void>, successKey: string) => {
    try {
      await action();
      setToast({ type: "success", title: t("success"), message: t(successKey) });
    } catch (err) {
      setToast({
        type: "error",
        title: t("error"),
        message: getErrorMessage(err, t("work_item_worklog.toast.error")),
      });
      throw err;
    }
  };

  const handleCreate = (payload: TIssueWorklogPayload) =>
    withToast(() => onCreate(payload), "work_item_worklog.toast.logged").catch(() => undefined);

  const handleUpdate = async (payload: TIssueWorklogPayload) => {
    if (!editingWorklogId) return;
    await withToast(() => onUpdate(editingWorklogId, payload), "work_item_worklog.toast.updated")
      .then(() => setEditingWorklogId(undefined))
      .catch(() => undefined);
  };

  const handleDelete = async () => {
    if (!deletingWorklogId) return;
    setIsDeleting(true);
    await withToast(() => onDelete(deletingWorklogId), "work_item_worklog.toast.deleted")
      .then(() => setDeletingWorklogId(undefined))
      .catch(() => undefined);
    setIsDeleting(false);
  };

  const handleClose = () => {
    setEditingWorklogId(undefined);
    onClose();
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent size="md">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>
                  {t("work_item_worklog.title")}: {formatWorklogDuration(totalDuration)}
                </DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody tabIndex={0}>
              <div className="space-y-5">
                {canLogTime && !editingWorklog && <IssueWorklogForm onSubmit={handleCreate} />}
                {editingWorklog && (
                  <div className="space-y-2">
                    <p className="text-body-xs-medium text-secondary">{t("work_item_worklog.edit_time_log")}</p>
                    <IssueWorklogForm
                      data={editingWorklog}
                      onSubmit={handleUpdate}
                      onCancel={() => setEditingWorklogId(undefined)}
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <p className="text-body-xs-medium text-secondary">{t("work_item_worklog.entries")}</p>
                  {worklogs.length === 0 ? (
                    <p className="text-body-xs-regular text-placeholder">{t("work_item_worklog.no_time_logged")}</p>
                  ) : (
                    <div className="divide-y divide-subtle rounded-md border border-subtle">
                      {worklogs.map((worklog) => {
                        const author = getUserDetails(worklog.logged_by_id);
                        const canManage = isProjectAdmin || worklog.logged_by_id === currentUser?.id;
                        return (
                          <div key={worklog.id} className="flex items-start gap-3 px-3 py-2">
                            <Avatar
                              size="sm"
                              alt={author?.display_name}
                              fallback={author?.display_name?.[0]?.toUpperCase()}
                              src={getFileURL(author?.avatar_url ?? "")}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2 text-body-xs-regular">
                                <span className="font-medium text-primary">
                                  {formatWorklogDuration(worklog.duration)}
                                </span>
                                <span className="text-secondary">{author?.display_name}</span>
                                <span className="text-placeholder">{renderFormattedDate(worklog.logged_at)}</span>
                              </div>
                              {worklog.description && (
                                <p className="mt-0.5 text-body-xs-regular break-words whitespace-pre-wrap text-tertiary">
                                  {worklog.description}
                                </p>
                              )}
                            </div>
                            {canManage && (
                              <div className="flex flex-shrink-0 items-center gap-1">
                                <IconButton
                                  variant="ghost"
                                  size="xs"
                                  aria-label={t("edit")}
                                  icon={<Icon icon={EditOutline} />}
                                  onClick={() => setEditingWorklogId(worklog.id)}
                                />
                                <IconButton
                                  variant="ghost"
                                  size="xs"
                                  aria-label={t("delete")}
                                  icon={<Icon icon={DeleteOutline} />}
                                  onClick={() => setDeletingWorklogId(worklog.id)}
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </DialogBody>
          </DialogMain>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        handleClose={() => setDeletingWorklogId(undefined)}
        handleSubmit={handleDelete}
        isSubmitting={isDeleting}
        isOpen={!!deletingWorklogId}
        title={t("work_item_worklog.delete.title")}
        content={t("work_item_worklog.delete.content")}
      />
    </>
  );
});
