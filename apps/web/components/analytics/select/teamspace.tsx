/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
// plane package imports
import { MembersOutline } from "@makeplane/propel/icons";
import { useTranslation } from "@plane/i18n";
import { Select } from "@plane/blocks/select";
import type { TLogoProps } from "@plane/types";
// hooks
import { TeamspaceLogo } from "@/components/teamspaces/logo";
import { useTeamspace } from "@/hooks/store/use-teamspace";

type TeamspaceOption = {
  id: string;
  name: string;
  logo_props?: TLogoProps;
};

type Props = {
  value: string[];
  onChange: (val: string[]) => void;
  teamspaceIds: string[] | undefined;
};

export const TeamspaceSelect = observer(function TeamspaceSelect(props: Props) {
  const { value, onChange, teamspaceIds } = props;
  const { t } = useTranslation();
  const { getTeamspaceById } = useTeamspace();

  // derived values
  const options = useMemo<TeamspaceOption[]>(
    () =>
      (teamspaceIds ?? []).map((teamspaceId) => {
        const teamspace = getTeamspaceById(teamspaceId);
        return { id: teamspaceId, name: teamspace?.name ?? teamspaceId, logo_props: teamspace?.logo_props };
      }),
    [teamspaceIds, getTeamspaceById]
  );
  const optionsById = useMemo(() => new Map(options.map((option) => [option.id, option])), [options]);
  const selected = useMemo(() => value.map((id) => optionsById.get(id) ?? { id, name: id }), [optionsById, value]);

  return (
    <Select<TeamspaceOption>
      multiple
      getValues={() => options}
      value={selected}
      onChange={(val) => onChange(val)}
      getOptionValue={(option) => option.id}
      getOptionLabel={(option) => option.name}
      getOptionIcon={(option) => <TeamspaceLogo logo={option.logo_props} size={16} />}
    >
      <Select.Trigger<TeamspaceOption>
        variant="select-md"
        className="w-auto"
        prependIcon={<MembersOutline aria-hidden="true" />}
      >
        {(selectedOptions) => (
          <span className="truncate">
            {selectedOptions.length > 2
              ? t("workspace_analytics.teamspaces.selected_count", { count: selectedOptions.length })
              : selectedOptions.length > 0
                ? selectedOptions.map((option) => option.name).join(", ")
                : t("workspace_analytics.teamspaces.all")}
          </span>
        )}
      </Select.Trigger>
    </Select>
  );
});
