/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// hooks
import { useAnalytics } from "@/hooks/store/use-analytics";
import { useProject } from "@/hooks/store/use-project";
import { useTeamspace } from "@/hooks/store/use-teamspace";
// components
import { ProjectSelect } from "./select/project";
import { TeamspaceSelect } from "./select/teamspace";

const AnalyticsFilterActions = observer(function AnalyticsFilterActions() {
  const { workspaceSlug } = useParams();
  const { selectedProjects, updateSelectedProjects, selectedTeamspaces, updateSelectedTeamspaces } = useAnalytics();
  const { joinedProjectIds } = useProject();
  const { fetchTeamspaces, getTeamspaceById, getWorkspaceTeamspaceIds } = useTeamspace();

  useSWR(workspaceSlug ? `WORKSPACE_TEAMSPACES_${workspaceSlug}` : null, () =>
    fetchTeamspaces(workspaceSlug!.toString())
  );
  const teamspaceIds = workspaceSlug ? getWorkspaceTeamspaceIds(workspaceSlug.toString()) : undefined;

  // when teamspaces are selected, only their projects can be picked
  const teamspaceProjectIds = useMemo(() => {
    if (selectedTeamspaces.length === 0) return undefined;
    return new Set(selectedTeamspaces.flatMap((id) => getTeamspaceById(id)?.project_ids ?? []));
  }, [selectedTeamspaces, getTeamspaceById]);
  const projectIds = useMemo(
    () => (teamspaceProjectIds ? joinedProjectIds?.filter((id) => teamspaceProjectIds.has(id)) : joinedProjectIds),
    [joinedProjectIds, teamspaceProjectIds]
  );

  const handleTeamspacesChange = (teamspaces: string[]) => {
    updateSelectedTeamspaces(teamspaces);
    if (teamspaces.length === 0) return;
    // drop selected projects that fall outside the new teamspace scope
    const allowed = new Set(teamspaces.flatMap((id) => getTeamspaceById(id)?.project_ids ?? []));
    const scopedProjects = selectedProjects.filter((id) => allowed.has(id));
    if (scopedProjects.length !== selectedProjects.length) updateSelectedProjects(scopedProjects);
  };

  return (
    <div className="flex items-center justify-end gap-2">
      {teamspaceIds && teamspaceIds.length > 0 && (
        <TeamspaceSelect value={selectedTeamspaces} onChange={handleTeamspacesChange} teamspaceIds={teamspaceIds} />
      )}
      <ProjectSelect
        value={selectedProjects}
        onChange={(val) => {
          updateSelectedProjects(val ?? []);
        }}
        projectIds={projectIds}
      />
      {/* <DurationDropdown
        buttonVariant="border-with-text"
        value={selectedDuration}
        onChange={(val) => {
          updateSelectedDuration(val);
        }}
        dropdownArrow
      /> */}
    </div>
  );
});

export default AnalyticsFilterActions;
