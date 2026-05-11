# Aeolus: download UK and standardise air quality data
# Copyright (C) 2025 Ruaraidh Dobson, South London Scientific
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Date-range helpers shared by the public API and submodules.

The ``last="30d"`` shorthand is used by ``aeolus.download``,
``aeolus.networks.download`` and ``aeolus.portals.download``; this is
the single implementation they all share.
"""

import re
from datetime import datetime, timedelta, timezone

_LAST_RE = re.compile(
    r"^(\d+)\s*"
    r"(min|mins|minute|minutes|h|hr|hrs|hour|hours"
    r"|d|day|days|w|week|weeks|m|month|months|y|year|years)$",
    re.I,
)

_LAST_UNITS = {
    "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
    "w": "weeks", "week": "weeks", "weeks": "weeks",
    "m": "months", "month": "months", "months": "months",
    "y": "years", "year": "years", "years": "years",
}


def parse_last(last: str) -> tuple[datetime, datetime]:
    """Parse a ``last="30d"`` shorthand into ``(start_date, end_date)``.

    Supported units: min/minute/minutes, h/hr/hrs/hour/hours,
    d/day/days, w/week/weeks, m/month/months, y/year/years.
    ``end_date`` is always now (UTC); ``start_date`` is
    ``end_date - duration``.
    """
    match = _LAST_RE.match(last.strip())
    if not match:
        raise ValueError(
            f"Invalid last value: {last!r}. "
            "Expected format like '6h', '30d', '2w', '6m', '1y'."
        )
    n = int(match.group(1))
    unit = _LAST_UNITS[match.group(2).lower()]

    end = datetime.now(tz=timezone.utc)

    if unit == "minutes":
        start = end - timedelta(minutes=n)
    elif unit == "hours":
        start = end - timedelta(hours=n)
    elif unit == "days":
        start = end - timedelta(days=n)
    elif unit == "weeks":
        start = end - timedelta(weeks=n)
    elif unit == "months":
        total_months = end.year * 12 + end.month - n
        y, m = divmod(total_months - 1, 12)
        m += 1
        day = min(
            end.day,
            [
                31,
                29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
            ][m - 1],
        )
        if y < 1:
            raise ValueError(f"Date range goes before year 1: last='{n}m'")
        start = end.replace(year=y, month=m, day=day)
    elif unit == "years":
        target_year = end.year - n
        if target_year < 1:
            raise ValueError(f"Date range goes before year 1: last='{n}y'")
        # Clamp Feb 29 → Feb 28 when the target year isn't a leap year so
        # parse_last("1y") on a leap day doesn't raise.
        if end.month == 2 and end.day == 29:
            is_leap = target_year % 4 == 0 and (
                target_year % 100 != 0 or target_year % 400 == 0
            )
            day = 29 if is_leap else 28
            start = end.replace(year=target_year, day=day)
        else:
            start = end.replace(year=target_year)
    else:
        raise ValueError(f"Unsupported unit: {unit}")

    return start, end


def resolve_dates(
    start_date: datetime | None,
    end_date: datetime | None,
    last: str | None,
) -> tuple[datetime, datetime]:
    """Resolve ``(start, end, last)`` arguments into a concrete date range.

    Either ``last`` or both of ``start_date``/``end_date`` must be set.
    """
    if last is not None:
        if start_date is not None or end_date is not None:
            raise ValueError(
                "Cannot use 'last' together with 'start_date'/'end_date'. "
                "Use one or the other."
            )
        return parse_last(last)
    if start_date is None or end_date is None:
        raise ValueError(
            "start_date and end_date are required "
            "(or use last='6h', last='30d', etc.)"
        )
    return start_date, end_date
