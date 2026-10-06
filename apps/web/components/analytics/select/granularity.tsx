/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { CalendarOutline } from "@makeplane/propel/icons";
// plane package imports
import { ANALYTICS_GRANULARITY_OPTIONS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Select } from "@plane/blocks/select";
import type { TAnalyticsGranularity } from "@plane/types";

type TGranularityOption = { value: TAnalyticsGranularity; label: string };

type Props = {
  value: TAnalyticsGranularity;
  onChange: (val: TAnalyticsGranularity) => void;
  /** Restrict the selectable buckets, e.g. `["day", "week"]` for period summaries. */
  allowed?: TAnalyticsGranularity[];
};

export function GranularitySelect({ value, onChange, allowed }: Props) {
  const { t } = useTranslation();

  const options = useMemo<TGranularityOption[]>(
    () =>
      ANALYTICS_GRANULARITY_OPTIONS.filter((option) => !allowed || allowed.includes(option.value)).map((option) => ({
        value: option.value,
        label: t(option.i18nKey),
      })),
    [allowed, t]
  );
  // an out-of-range stored value (e.g. "month" where only day/week apply) falls back to the last allowed bucket
  const selected = options.find((option) => option.value === value) ?? options[options.length - 1] ?? null;

  return (
    <Select<TGranularityOption>
      getValues={() => options}
      value={selected}
      onChange={(val) => {
        const option = options.find((o) => o.value === val);
        if (option) onChange(option.value);
      }}
      getOptionValue={(option) => option.value}
      getOptionLabel={(option) => option.label}
      pinSelected={false}
    >
      <Select.Trigger<TGranularityOption> variant="select-md" prependIcon={<CalendarOutline aria-hidden="true" />}>
        {(selectedOptions) => <span className="truncate">{selectedOptions[0]?.label}</span>}
      </Select.Trigger>
    </Select>
  );
}
