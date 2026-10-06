/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TTeamspace, TTeamspacePayload } from "@plane/types";
// components
import { MemberSelect } from "@/components/dropdowns/member/member-select";
import { ProjectSelect } from "@/components/dropdowns/project/project-select";
// hooks
import { useTeamspace } from "@/hooks/store/use-teamspace";

type TTeamspaceFormValues = {
  name: string;
  description: string;
  lead_id: string | null;
  member_ids: string[];
  project_ids: string[];
};

type Props = {
  workspaceSlug: string;
  isOpen: boolean;
  onClose: () => void;
  /** Teamspace being edited; omit to create a new one. */
  data?: TTeamspace;
};

const getDefaultValues = (data?: TTeamspace): TTeamspaceFormValues => ({
  name: data?.name ?? "",
  description: data?.description ?? "",
  lead_id: data?.lead_id ?? null,
  member_ids: data?.member_ids ?? [],
  project_ids: data?.project_ids ?? [],
});

const getErrorMessage = (err: unknown, fallback: string) =>
  err && typeof err === "object" && "error" in err && typeof err.error === "string" && err.error ? err.error : fallback;

export const TeamspaceFormModal = observer(function TeamspaceFormModal(props: Props) {
  const { workspaceSlug, isOpen, onClose, data } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { createTeamspace, updateTeamspace } = useTeamspace();
  // form
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    reset,
  } = useForm<TTeamspaceFormValues>({ defaultValues: getDefaultValues(data) });

  useEffect(() => {
    if (isOpen) reset(getDefaultValues(data));
  }, [data, isOpen, reset]);

  const handleFormSubmit = async (values: TTeamspaceFormValues) => {
    const payload: TTeamspacePayload = {
      name: values.name.trim(),
      description: values.description,
      lead_id: values.lead_id || null,
      member_ids: values.member_ids,
      project_ids: values.project_ids,
    };
    try {
      if (data) await updateTeamspace(workspaceSlug, data.id, payload);
      else await createTeamspace(workspaceSlug, payload);
      setToast({
        type: "success",
        title: t("success"),
        message: t(
          data
            ? "workspace_settings.settings.teamspaces.toast.updated"
            : "workspace_settings.settings.teamspaces.toast.created"
        ),
      });
      onClose();
    } catch (err) {
      setToast({
        type: "error",
        title: t("error"),
        message: getErrorMessage(err, t("workspace_settings.settings.teamspaces.toast.error")),
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent size="md">
        <form onSubmit={handleSubmit(handleFormSubmit)} className="flex min-h-0 flex-1 flex-col">
          <DialogMain>
            <DialogHeader>
              <DialogHeading>
                <DialogTitle>
                  {t(
                    data
                      ? "workspace_settings.settings.teamspaces.edit_teamspace"
                      : "workspace_settings.settings.teamspaces.create_teamspace"
                  )}
                </DialogTitle>
              </DialogHeading>
            </DialogHeader>
            <DialogBody tabIndex={0}>
              <div className="space-y-3">
                <Controller
                  control={control}
                  name="name"
                  rules={{
                    required: t("title_is_required"),
                    maxLength: { value: 255, message: t("title_should_be_less_than_255_characters") },
                    validate: (val) => val.trim() !== "" || t("title_is_required"),
                  }}
                  render={({ field: { value, onChange, ref } }) => (
                    <InputField
                      type="text"
                      size="2xl"
                      orientation="vertical"
                      value={value}
                      onChange={onChange}
                      ref={ref}
                      error={errors.name?.message}
                      placeholder={t("workspace_settings.settings.teamspaces.name_placeholder")}
                      aria-label={t("name")}
                    />
                  )}
                />
                <Controller
                  control={control}
                  name="description"
                  render={({ field: { value, onChange } }) => (
                    <TextAreaField
                      size="lg"
                      resize="none"
                      autoResize
                      maxRows={6}
                      value={value}
                      onChange={onChange}
                      placeholder={t("workspace_settings.settings.teamspaces.description_placeholder")}
                      aria-label={t("description")}
                    />
                  )}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Controller
                    control={control}
                    name="lead_id"
                    render={({ field: { value, onChange } }) => (
                      <MemberSelect
                        multiple={false}
                        value={value}
                        onChange={(id) => onChange(id || null)}
                        clearable
                        clearLabel={t("workspace_settings.settings.teamspaces.no_lead")}
                        placeholder={t("workspace_settings.settings.teamspaces.lead")}
                        variant="pill-md"
                      />
                    )}
                  />
                  <Controller
                    control={control}
                    name="member_ids"
                    render={({ field: { value, onChange } }) => (
                      <MemberSelect
                        multiple
                        value={value ?? []}
                        onChange={onChange}
                        placeholder={t("workspace_settings.settings.teamspaces.members")}
                        variant={value?.length ? "avatar-group-md" : "pill-md"}
                      />
                    )}
                  />
                  <Controller
                    control={control}
                    name="project_ids"
                    render={({ field: { value, onChange } }) => (
                      <ProjectSelect
                        multiple
                        projectList="all"
                        value={value ?? []}
                        onChange={onChange}
                        placeholder={t("workspace_settings.settings.teamspaces.projects")}
                        variant="pill-md"
                      />
                    )}
                  />
                </div>
              </div>
            </DialogBody>
          </DialogMain>
          <DialogActions>
            <Button variant="secondary" size="sm" stretch="auto" label={t("cancel")} onClick={onClose} />
            <Button
              variant="primary"
              type="submit"
              size="sm"
              stretch="auto"
              label={
                data
                  ? isSubmitting
                    ? t("updating")
                    : t("update")
                  : isSubmitting
                    ? t("creating")
                    : t("workspace_settings.settings.teamspaces.create_teamspace")
              }
              loading={isSubmitting}
            />
          </DialogActions>
        </form>
      </DialogContent>
    </Dialog>
  );
});
