/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback } from "react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { convertMinutesToHoursMinutesString } from "@plane/utils";

/**
 * Returns a formatter for durations in minutes using the current locale's units, e.g. `2h 30m` / `2 Std. 30 Min.`.
 * Like `convertMinutesToHoursMinutesString`, a zero duration renders as an empty string.
 */
export const useDurationFormatter = () => {
  const { t } = useTranslation();

  return useCallback(
    (totalMinutes: number) =>
      convertMinutesToHoursMinutesString(totalMinutes, {
        hours: (count) => t("common.duration_units.hours", { count }),
        minutes: (count) => t("common.duration_units.minutes", { count }),
      }),
    [t]
  );
};
