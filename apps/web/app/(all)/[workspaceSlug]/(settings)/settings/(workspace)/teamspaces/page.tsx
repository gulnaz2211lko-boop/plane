/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@makeplane/propel/components/button";
import { EmptyStateCompact } from "@plane/blocks/empty-state";
// components
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { DeleteTeamspaceModal, TeamspaceFormModal, TeamspaceListItem } from "@/components/teamspaces";
import { WebhookSettingsLoader } from "@/components/ui/loader/settings/web-hook";
// hooks
import { useTeamspace } from "@/hooks/store/use-teamspace";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import type { Route } from "./+types/page";
import { TeamspacesWorkspaceSettingsHeader } from "./header";

function TeamspacesSettingsPage({ params }: Route.ComponentProps) {
  // router
  const { workspaceSlug } = params;
  // states
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingTeamspaceId, setEditingTeamspaceId] = useState<string | undefined>(undefined);
  const [deletingTeamspaceId, setDeletingTeamspaceId] = useState<string | undefined>(undefined);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { workspaceUserInfo, allowPermissions } = useUserPermissions();
  const { currentWorkspace } = useWorkspace();
  const { fetchTeamspaces, getWorkspaceTeamspaceIds, getTeamspaceById } = useTeamspace();
  // derived values
  const canViewTeamspaces = allowPermissions(
    [EUserPermissions.ADMIN, EUserPermissions.MEMBER],
    EUserPermissionsLevel.WORKSPACE
  );
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const teamspaceIds = getWorkspaceTeamspaceIds(workspaceSlug);
  const pageTitle = currentWorkspace?.name
    ? `${currentWorkspace.name} - ${t("workspace_settings.settings.teamspaces.title")}`
    : undefined;

  useSWR(
    canViewTeamspaces ? `WORKSPACE_TEAMSPACES_${workspaceSlug}` : null,
    canViewTeamspaces ? () => fetchTeamspaces(workspaceSlug) : null
  );

  const openCreateModal = () => {
    setEditingTeamspaceId(undefined);
    setIsFormOpen(true);
  };

  if (workspaceUserInfo && !canViewTeamspaces) {
    return <NotAuthorizedView section="settings" className="h-auto" />;
  }

  if (!teamspaceIds) return <WebhookSettingsLoader />;

  return (
    <SettingsContentWrapper header={<TeamspacesWorkspaceSettingsHeader />}>
      <PageHead title={pageTitle} />
      <TeamspaceFormModal
        workspaceSlug={workspaceSlug}
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        data={editingTeamspaceId ? getTeamspaceById(editingTeamspaceId) : undefined}
      />
      <DeleteTeamspaceModal
        workspaceSlug={workspaceSlug}
        isOpen={!!deletingTeamspaceId}
        onClose={() => setDeletingTeamspaceId(undefined)}
        data={deletingTeamspaceId ? getTeamspaceById(deletingTeamspaceId) : undefined}
      />
      <div className="w-full">
        <SettingsHeading
          title={t("workspace_settings.settings.teamspaces.heading")}
          description={
            isAdmin
              ? t("workspace_settings.settings.teamspaces.description")
              : `${t("workspace_settings.settings.teamspaces.description")} ${t("workspace_settings.settings.teamspaces.only_admins_can_manage")}`
          }
          control={
            isAdmin ? (
              <Button
                variant="primary"
                size="md"
                stretch="auto"
                label={t("workspace_settings.settings.teamspaces.add_teamspace")}
                onClick={openCreateModal}
              />
            ) : undefined
          }
        />
        {teamspaceIds.length > 0 ? (
          <div className="mt-4 rounded-lg border border-subtle">
            {teamspaceIds.map((teamspaceId) => (
              <TeamspaceListItem
                key={teamspaceId}
                teamspaceId={teamspaceId}
                isAdmin={isAdmin}
                onEdit={(id) => {
                  setEditingTeamspaceId(id);
                  setIsFormOpen(true);
                }}
                onDelete={(id) => setDeletingTeamspaceId(id)}
              />
            ))}
          </div>
        ) : (
          <EmptyStateCompact
            assetKey="members"
            title={t("workspace_settings.settings.teamspaces.empty_state.title")}
            description={t("workspace_settings.settings.teamspaces.empty_state.description")}
            actions={
              isAdmin
                ? [{ label: t("workspace_settings.settings.teamspaces.add_teamspace"), onClick: openCreateModal }]
                : undefined
            }
            align="start"
            rootClassName="py-20"
          />
        )}
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(TeamspacesSettingsPage);
