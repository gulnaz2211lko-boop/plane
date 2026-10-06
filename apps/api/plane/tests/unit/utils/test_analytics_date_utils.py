# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the bucketing / period / filter helpers behind project and time tracking analytics."""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from plane.app.views.analytic.advance import minutes_to_hours, utilization_percentage
from plane.utils.date_utils import (
    align_to_bucket,
    date_range_filter,
    get_bucket_starts,
    get_datetime_bounds,
    get_default_series_start,
    get_granularity,
    get_period_ranges,
    next_bucket,
    parse_id_list,
    to_date,
)


@pytest.mark.unit
class TestParseIdList:
    def test_empty_values(self):
        assert parse_id_list(None) == []
        assert parse_id_list("") == []
        assert parse_id_list([]) == []

    def test_drops_blanks_and_non_uuids(self):
        first, second = str(uuid.uuid4()), str(uuid.uuid4())
        assert parse_id_list(f"{first},, not-a-uuid ,{second},1' OR 1=1") == [first, second]

    def test_normalizes_whitespace_and_case(self):
        value = uuid.uuid4()
        assert parse_id_list(f"  {str(value).upper()}  ") == [str(value)]

    def test_accepts_lists(self):
        value = uuid.uuid4()
        assert parse_id_list([value, "junk"]) == [str(value)]


@pytest.mark.unit
class TestGranularity:
    @pytest.mark.parametrize("value", ["day", "week", "month"])
    def test_valid_values_pass_through(self, value):
        assert get_granularity(value) == value

    @pytest.mark.parametrize("value", [None, "", "year", "DAY", "week "])
    def test_invalid_values_fall_back(self, value):
        assert get_granularity(value) == "month"
        assert get_granularity(value, default="week") == "week"


@pytest.mark.unit
class TestBuckets:
    def test_align_to_bucket(self):
        wednesday = date(2030, 3, 13)
        assert align_to_bucket(wednesday, "day") == wednesday
        assert align_to_bucket(wednesday, "week") == date(2030, 3, 11)
        assert align_to_bucket(wednesday, "month") == date(2030, 3, 1)

    def test_week_alignment_is_stable_on_monday_and_sunday(self):
        assert align_to_bucket(date(2030, 3, 11), "week") == date(2030, 3, 11)
        assert align_to_bucket(date(2030, 3, 17), "week") == date(2030, 3, 11)

    def test_week_alignment_crosses_year_boundary(self):
        # 1 Jan 2030 is a Tuesday, so its week starts in the previous year.
        assert align_to_bucket(date(2030, 1, 1), "week") == date(2029, 12, 31)

    def test_next_bucket(self):
        assert next_bucket(date(2028, 2, 28), "day") == date(2028, 2, 29)  # leap year
        assert next_bucket(date(2029, 12, 31), "week") == date(2030, 1, 7)
        assert next_bucket(date(2029, 12, 1), "month") == date(2030, 1, 1)
        assert next_bucket(date(2030, 1, 1), "month") == date(2030, 2, 1)

    def test_bucket_starts_include_partial_first_and_last_buckets(self):
        assert get_bucket_starts(date(2029, 12, 30), date(2030, 1, 2), "week") == [
            date(2029, 12, 24),
            date(2029, 12, 31),
        ]
        assert get_bucket_starts(date(2029, 11, 15), date(2030, 2, 1), "month") == [
            date(2029, 11, 1),
            date(2029, 12, 1),
            date(2030, 1, 1),
            date(2030, 2, 1),
        ]

    def test_bucket_starts_single_day_and_inverted_range(self):
        day = date(2030, 3, 13)
        assert get_bucket_starts(day, day, "day") == [day]
        assert get_bucket_starts(day, day - timedelta(days=1), "day") == []

    def test_to_date(self):
        assert to_date(datetime(2030, 3, 13, 23, 59)) == date(2030, 3, 13)
        assert to_date(date(2030, 3, 13)) == date(2030, 3, 13)


@pytest.mark.unit
class TestDefaultSeriesStart:
    def test_day_covers_thirty_days(self):
        today = date(2030, 3, 13)
        start = get_default_series_start("day", today)
        assert start == date(2030, 2, 12)
        assert len(get_bucket_starts(start, today, "day")) == 30

    def test_week_covers_twelve_weeks_from_a_monday(self):
        today = date(2030, 3, 13)
        start = get_default_series_start("week", today)
        assert start == date(2029, 12, 24)
        assert start.weekday() == 0
        assert len(get_bucket_starts(start, today, "week")) == 12

    def test_month_covers_twelve_months_across_the_year_boundary(self):
        today = date(2030, 1, 15)
        start = get_default_series_start("month", today)
        assert start == date(2029, 2, 1)
        assert len(get_bucket_starts(start, today, "month")) == 12


@pytest.mark.unit
class TestPeriodRanges:
    def test_day(self):
        assert get_period_ranges("day", date(2030, 1, 1)) == {
            "current": (date(2030, 1, 1), date(2030, 1, 1)),
            "previous": (date(2029, 12, 31), date(2029, 12, 31)),
        }

    def test_week(self):
        assert get_period_ranges("week", date(2030, 3, 13)) == {
            "current": (date(2030, 3, 11), date(2030, 3, 17)),
            "previous": (date(2030, 3, 4), date(2030, 3, 10)),
        }

    def test_month_in_january_compares_with_december(self):
        assert get_period_ranges("month", date(2030, 1, 15)) == {
            "current": (date(2030, 1, 1), date(2030, 1, 31)),
            "previous": (date(2029, 12, 1), date(2029, 12, 31)),
        }

    def test_month_after_a_leap_february(self):
        assert get_period_ranges("month", date(2028, 3, 31))["previous"] == (date(2028, 2, 1), date(2028, 2, 29))

    @pytest.mark.parametrize("granularity", ["day", "week", "month"])
    def test_periods_are_adjacent_and_do_not_overlap(self, granularity):
        ranges = get_period_ranges(granularity, date(2030, 3, 13))
        assert ranges["previous"][1] + timedelta(days=1) == ranges["current"][0]


@pytest.mark.unit
class TestDateRangeFilter:
    def test_datetime_lookup_becomes_half_open_timestamp_range(self):
        with timezone.override(ZoneInfo("UTC")):
            filters = date_range_filter("created_at__date", date(2030, 3, 11), date(2030, 3, 12))
        assert filters == {
            "created_at__gte": datetime(2030, 3, 11, tzinfo=ZoneInfo("UTC")),
            "created_at__lt": datetime(2030, 3, 13, tzinfo=ZoneInfo("UTC")),
        }

    def test_relation_prefix_is_kept(self):
        with timezone.override(ZoneInfo("UTC")):
            filters = date_range_filter("issue__completed_at__date", date(2030, 3, 11), date(2030, 3, 11))
        assert set(filters) == {"issue__completed_at__gte", "issue__completed_at__lt"}

    def test_plain_date_field_is_compared_inclusively(self):
        assert date_range_filter("logged_at", date(2030, 3, 11), date(2030, 3, 12)) == {
            "logged_at__gte": date(2030, 3, 11),
            "logged_at__lte": date(2030, 3, 12),
        }

    def test_bounds_follow_the_active_timezone(self):
        with timezone.override(ZoneInfo("Asia/Tokyo")):
            lower, upper = get_datetime_bounds(date(2030, 3, 11), date(2030, 3, 11))
        # Midnight in Tokyo is 15:00 UTC on the previous day.
        assert lower == datetime(2030, 3, 10, 15, tzinfo=ZoneInfo("UTC"))
        assert upper == datetime(2030, 3, 11, 15, tzinfo=ZoneInfo("UTC"))

    def test_bounds_on_a_daylight_saving_day(self):
        # Clocks go forward on 10 Mar 2030 in New York, so that local day is 23 hours long.
        with timezone.override(ZoneInfo("America/New_York")):
            lower, upper = get_datetime_bounds(date(2030, 3, 10), date(2030, 3, 10))
        # Subtracting two datetimes in the same zone ignores the offset change, so compare in UTC.
        assert upper.astimezone(ZoneInfo("UTC")) - lower.astimezone(ZoneInfo("UTC")) == timedelta(hours=23)


@pytest.mark.unit
class TestTimeMath:
    def test_minutes_to_hours(self):
        assert minutes_to_hours(None) == 0
        assert minutes_to_hours(0) == 0
        assert minutes_to_hours(90) == 1.5
        assert minutes_to_hours(100) == 1.67

    def test_utilization_percentage(self):
        assert utilization_percentage(30, None) is None
        assert utilization_percentage(30, 0) is None
        assert utilization_percentage(None, 60) == 0.0
        assert utilization_percentage(30, 60) == 50.0
        assert utilization_percentage(90, 60) == 150.0
        assert utilization_percentage(1, 3) == 33.3
