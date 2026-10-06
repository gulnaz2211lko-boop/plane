/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { ConfirmDialog } from "@plane/blocks/dialog";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TTeamspace } from "@plane/types";
// hooks
import { useTeamspace } from "@/hooks/store/use-teamspace";

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  data: TTeamspace | undefined;
};

export const DeleteTeamspaceModal = observer(function DeleteTeamspaceModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, data } = props;
  // states
  const [isDeleting, setIsDeleting] = useState(false);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { deleteTeamspace } = useTeamspace();

  const handleClose = () => {
    onClose();
    setIsDeleting(false);
  };

  const handleDelete = async () => {
    if (!data) return;
    setIsDeleting(true);
    try {
      await deleteTeamspace(workspaceSlug, data.id);
      setToast({
        type: "success",
        title: t("success"),
        message: t("workspace_settings.settings.teamspaces.toast.deleted"),
      });
      handleClose();
    } catch {
      setIsDeleting(false);
      setToast({
        type: "error",
        title: t("error"),
        message: t("workspace_settings.settings.teamspaces.toast.error"),
      });
    }
  };

  return (
    <ConfirmDialog
      handleClose={handleClose}
      handleSubmit={handleDelete}
      isSubmitting={isDeleting}
      isOpen={isOpen}
      title={t("workspace_settings.settings.teamspaces.delete.title")}
      content={t("workspace_settings.settings.teamspaces.delete.content", { name: data?.name ?? "" })}
    />
  );
});
