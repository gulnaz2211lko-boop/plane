/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTranslation } from "@plane/i18n";
import { convertMinutesToHoursAndMinutes } from "@plane/utils";

type TEstimateTimeInputProps = {
  /** total minutes */
  value?: number;
  /** emits the total minutes as a string ("" when both fields are empty) */
  handleEstimateInputValue: (value: string) => void;
};

const parsePart = (value: string): number => {
  const parsed = parseInt(value, 10);
  return isNaN(parsed) || parsed < 0 ? 0 : parsed;
};

export function EstimateTimeInput(props: TEstimateTimeInputProps) {
  const { value, handleEstimateInputValue } = props;

  // i18n
  const { t } = useTranslation();

  // derived values
  const { hours, minutes } = value && !isNaN(value) ? convertMinutesToHoursAndMinutes(value) : { hours: 0, minutes: 0 };

  const handleChange = (nextHours: number, nextMinutes: number) => {
    const total = nextHours * 60 + nextMinutes;
    handleEstimateInputValue(total > 0 ? total.toString() : "");
  };

  const inputClassName =
    "w-16 border-none bg-transparent px-2 py-2 text-13 focus:border-0 focus:ring-0 focus:outline-none";

  return (
    <div className="flex w-full items-center gap-1 text-13 text-secondary">
      <input
        type="number"
        min={0}
        value={value ? hours : ""}
        onChange={(e) => handleChange(parsePart(e.target.value), minutes)}
        className={inputClassName}
        placeholder="0"
        aria-label={t("project_settings.estimates.create.hours")}
      />
      <span>{t("project_settings.estimates.create.hours_short")}</span>
      <input
        type="number"
        min={0}
        max={59}
        value={value ? minutes : ""}
        onChange={(e) => handleChange(hours, Math.min(parsePart(e.target.value), 59))}
        className={inputClassName}
        placeholder="0"
        aria-label={t("project_settings.estimates.create.minutes")}
      />
      <span>{t("project_settings.estimates.create.minutes_short")}</span>
    </div>
  );
}
