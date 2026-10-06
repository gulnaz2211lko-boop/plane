/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { CalendarOutline } from "@makeplane/propel/icons";
import { DateSelect } from "@plane/blocks/property-select";
import { useTranslation } from "@plane/i18n";
import type { TIssueWorklog, TIssueWorklogPayload } from "@plane/types";
import { convertMinutesToHoursAndMinutes, getDate, renderFormattedPayloadDate } from "@plane/utils";
// hooks
import { useUserProfile } from "@/hooks/store/user";

type TWorklogFormValues = {
  hours: string;
  minutes: string;
  logged_at: Date | null;
  description: string;
};

type Props = {
  /** Entry being edited; omit to log a new one. */
  data?: TIssueWorklog;
  onSubmit: (payload: TIssueWorklogPayload) => Promise<void>;
  onCancel?: () => void;
};

const getDefaultValues = (data?: TIssueWorklog): TWorklogFormValues => {
  const { hours, minutes } = convertMinutesToHoursAndMinutes(data?.duration ?? 0);
  return {
    hours: data ? String(hours) : "",
    minutes: data ? String(minutes) : "",
    logged_at: (data ? getDate(data.logged_at) : undefined) ?? new Date(),
    description: data?.description ?? "",
  };
};

const toNonNegativeInt = (value: string) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
};

export function IssueWorklogForm(props: Props) {
  const { data, onSubmit, onCancel } = props;
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const { data: userProfile } = useUserProfile();
  // form
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    reset,
    setError,
  } = useForm<TWorklogFormValues>({ defaultValues: getDefaultValues(data) });

  useEffect(() => {
    reset(getDefaultValues(data));
  }, [data, reset]);

  const handleFormSubmit = async (values: TWorklogFormValues) => {
    const duration = toNonNegativeInt(values.hours) * 60 + toNonNegativeInt(values.minutes);
    if (duration <= 0) {
      setError("hours", { message: t("work_item_worklog.duration_required") });
      return;
    }
    await onSubmit({
      duration,
      logged_at: renderFormattedPayloadDate(values.logged_at ?? new Date()),
      description: values.description.trim(),
    });
    if (!data) reset(getDefaultValues());
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="w-24">
          <Controller
            control={control}
            name="hours"
            render={({ field: { value, onChange, ref } }) => (
              <InputField
                type="number"
                min={0}
                size="xl"
                orientation="vertical"
                label={t("work_item_worklog.hours")}
                value={value}
                onChange={onChange}
                ref={ref}
                error={errors.hours?.message}
                placeholder="0"
              />
            )}
          />
        </div>
        <div className="w-24">
          <Controller
            control={control}
            name="minutes"
            render={({ field: { value, onChange, ref } }) => (
              <InputField
                type="number"
                min={0}
                max={59}
                size="xl"
                orientation="vertical"
                label={t("work_item_worklog.minutes")}
                value={value}
                onChange={onChange}
                ref={ref}
                placeholder="0"
              />
            )}
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-body-xs-medium text-secondary">{t("work_item_worklog.date")}</span>
          <Controller
            control={control}
            name="logged_at"
            render={({ field: { value, onChange } }) => (
              <DateSelect
                value={value}
                onChange={(date) => onChange(date)}
                maxDate={new Date()}
                icon={<CalendarOutline />}
                placeholder={t("work_item_worklog.date")}
                weekStartsOn={userProfile?.start_of_the_week}
                variant="pill-md"
              />
            )}
          />
        </div>
      </div>
      <Controller
        control={control}
        name="description"
        render={({ field: { value, onChange } }) => (
          <TextAreaField
            size="lg"
            resize="none"
            autoResize
            maxRows={4}
            value={value}
            onChange={onChange}
            placeholder={t("work_item_worklog.description_placeholder")}
            aria-label={t("description")}
          />
        )}
      />
      <div className="flex items-center justify-end gap-2">
        {onCancel && <Button variant="secondary" size="sm" stretch="auto" label={t("cancel")} onClick={onCancel} />}
        <Button
          variant="primary"
          type="submit"
          size="sm"
          stretch="auto"
          label={data ? t("update") : t("work_item_worklog.log_time")}
          loading={isSubmitting}
        />
      </div>
    </form>
  );
}
