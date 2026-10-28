# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""When a subscription runs next."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from auto_ontology.dal import schema as s

_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

WEEKDAY_NAMES = ("一", "二", "三", "四", "五", "六", "日")


class ScheduleError(ValueError):
    """An invalid schedule; the message is user-facing."""


def _zone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleError(f"未知的时区：{name}") from exc


def validate(schedule: str, time_of_day: str, weekday: int | None, tz: str) -> None:
    if schedule not in s.SCHEDULES:
        raise ScheduleError("未知的推送频率")
    if not _TIME.match(time_of_day or ""):
        raise ScheduleError("时间格式应为 HH:MM，例如 09:00")
    if schedule == s.SCHEDULE_WEEKLY and weekday not in range(1, 8):
        raise ScheduleError("每周推送需要选择星期几")
    _zone(tz)


def next_run(
    schedule: str,
    time_of_day: str,
    weekday: int | None,
    tz: str,
    after: datetime,
) -> datetime:
    """The first run strictly after *after*, in UTC.

    ``hourly`` uses only the minute of *time_of_day*; ``weekly`` runs on
    *weekday* (1 = Monday … 7 = Sunday); ``workdays`` is Monday to Friday.
    """
    validate(schedule, time_of_day, weekday, tz)
    zone = _zone(tz)
    hour, minute = (int(x) for x in time_of_day.split(":"))
    local = after.astimezone(zone)
    if schedule == s.SCHEDULE_HOURLY:
        candidate = local.replace(minute=minute, second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(hours=1)
        return candidate.astimezone(timezone.utc)
    day = local.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(0, 9):
        date = (day + timedelta(days=offset)).date()
        # Built from the wall-clock date so DST changes keep the local time.
        candidate = datetime(date.year, date.month, date.day, hour, minute, tzinfo=zone)
        if candidate <= local:
            continue
        iso_weekday = candidate.isoweekday()
        if schedule == s.SCHEDULE_WORKDAYS and iso_weekday > 5:
            continue
        if schedule == s.SCHEDULE_WEEKLY and iso_weekday != weekday:
            continue
        return candidate.astimezone(timezone.utc)
    raise AssertionError("unreachable: a week always holds a matching day")


def describe(schedule: str, time_of_day: str, weekday: int | None) -> str:
    """The schedule in words, e.g. ``每周一 09:00``."""
    if schedule == s.SCHEDULE_HOURLY:
        return f"每小时第 {time_of_day[-2:]} 分"
    if schedule == s.SCHEDULE_WORKDAYS:
        return f"工作日 {time_of_day}"
    if schedule == s.SCHEDULE_WEEKLY and weekday:
        return f"每周{WEEKDAY_NAMES[weekday - 1]} {time_of_day}"
    return f"每天 {time_of_day}"
