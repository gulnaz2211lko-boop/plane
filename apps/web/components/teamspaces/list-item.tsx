/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { Avatar } from "@makeplane/propel/components/avatar";
import { AvatarGroup } from "@makeplane/propel/components/avatar-group";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Tooltip } from "@makeplane/propel/components/tooltip";
import { DeleteOutline, EditOutline } from "@makeplane/propel/icons";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { useTranslation } from "@plane/i18n";
import { getFileURL } from "@plane/utils";
// hooks
import { useMember } from "@/hooks/store/use-member";
import { useProject } from "@/hooks/store/use-project";
import { useTeamspace } from "@/hooks/store/use-teamspace";
// local imports
import { TeamspaceLogo } from "./logo";

type Props = {
  teamspaceId: string;
  isAdmin: boolean;
  onEdit: (teamspaceId: string) => void;
  onDelete: (teamspaceId: string) => void;
};

export const TeamspaceListItem = observer(function TeamspaceListItem(props: Props) {
  const { teamspaceId, isAdmin, onEdit, onDelete } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { getTeamspaceById } = useTeamspace();
  const { getUserDetails } = useMember();
  const { getProjectById } = useProject();
  // derived values
  const teamspace = getTeamspaceById(teamspaceId);
  if (!teamspace) return null;
  const lead = teamspace.lead_id ? getUserDetails(teamspace.lead_id) : undefined;
  const members = teamspace.member_ids.map((id) => getUserDetails(id)).filter((member) => !!member);
  const projects = teamspace.project_ids.map((id) => getProjectById(id)).filter((project) => !!project);

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-subtle px-4 py-3 last:border-b-0">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex size-8 flex-shrink-0 items-center justify-center rounded-md bg-layer-1">
          <TeamspaceLogo logo={teamspace.logo_props} size={16} />
        </div>
        <div className="min-w-0">
          <p className="truncate text-13 font-medium text-primary">{teamspace.name}</p>
          {teamspace.description && <p className="truncate text-12 text-tertiary">{teamspace.description}</p>}
        </div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-4 text-12 text-secondary">
        {lead && (
          <Tooltip label={`${t("workspace_settings.settings.teamspaces.lead")}: ${lead.display_name}`}>
            <span className="flex items-center gap-1.5">
              <Avatar
                size="sm"
                alt={lead.display_name}
                fallback={lead.display_name?.[0]?.toUpperCase()}
                src={getFileURL(lead.avatar_url)}
              />
              <span className="hidden truncate sm:inline">{lead.display_name}</span>
            </span>
          </Tooltip>
        )}
        <span className="flex items-center gap-1.5">
          {members.length > 0 && (
            <AvatarGroup size="xs" max={3}>
              {members.map((member) => (
                <Avatar
                  key={member.id}
                  alt={member.display_name}
                  fallback={member.display_name?.[0]?.toUpperCase()}
                  src={getFileURL(member.avatar_url)}
                />
              ))}
            </AvatarGroup>
          )}
          {t("workspace_settings.settings.teamspaces.members_count", { count: teamspace.member_ids.length })}
        </span>
        <Tooltip label={projects.map((project) => project.name).join(", ")} disabled={projects.length === 0}>
          <span className="flex items-center gap-1.5">
            {projects.slice(0, 3).map((project) => (
              <Logo key={project.id} logo={project.logo_props} size={14} />
            ))}
            {t("workspace_settings.settings.teamspaces.projects_count", { count: teamspace.project_ids.length })}
          </span>
        </Tooltip>
        {isAdmin && (
          <div className="flex items-center gap-1">
            <IconButton
              variant="ghost"
              size="sm"
              aria-label={t("edit")}
              icon={<Icon icon={EditOutline} />}
              onClick={() => onEdit(teamspace.id)}
            />
            <IconButton
              variant="ghost"
              size="sm"
              aria-label={t("delete")}
              icon={<Icon icon={DeleteOutline} />}
              onClick={() => onDelete(teamspace.id)}
            />
          </div>
        )}
      </div>
    </div>
  );
});
