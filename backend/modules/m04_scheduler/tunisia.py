"""Tunisian occasions for the outfit calendar (BO6): public holidays, Islamic feasts, seasons.

Islamic dates use the arithmetic (tabular) Hijri calendar: they can differ by about one day from the official
date, which depends on the moon sighting announced by the Mufti. They are flagged `approximate`.
"""

from __future__ import annotations

import datetime as dt

# fixed-date national days (occasion = what you would dress for)
FIXED = [
    (1, 1, "New Year's Day", "casual", None),
    (3, 20, "Independence Day", "casual", None),
    (4, 9, "Martyrs' Day", "casual", None),
    (5, 1, "Labour Day", "casual", None),
    (7, 25, "Republic Day", "casual", None),
    (8, 13, "Women's Day", "event", "festive"),
    (10, 15, "Evacuation Day", "casual", None),
    (12, 17, "Revolution Day", "casual", None),
]
# (hijri month, day, name, occasion, dress code, number of days)
ISLAMIC = [
    (1, 1, "Ras el Am el Hijri (Islamic New Year)", "casual", None, 1),
    (3, 12, "Mouled (Prophet's Birthday)", "event", "traditional", 1),
    (9, 1, "First day of Ramadan", "casual", "modest", 1),
    (10, 1, "Aid el Fitr", "event", "traditional or festive (jebba, kaftan, new clothes)", 2),
    (12, 10, "Aid el Kebir (Aid el Adha)", "event", "traditional or festive", 2),
]
# periods that change what people wear
SEASONS = [
    ("Summer wedding season", 6, 1, 9, 30, "event", "evening / festive"),
]
_EPOCH = 1948440  # Julian day number of 1 Muharram 1 AH (arithmetic calendar)


def _hijri_to_jdn(y: int, m: int, d: int) -> int:
    return d + (59 * (m - 1) + 1) // 2 + (y - 1) * 354 + (3 + 11 * y) // 30 + _EPOCH - 1


def _jdn_to_greg(j: int) -> dt.date:
    return dt.date.fromordinal(j - 1721425)


def _greg_to_hijri_year(day: dt.date) -> int:
    j = day.toordinal() + 1721425
    return (30 * (j - _EPOCH) + 10646) // 10631


def hijri_to_gregorian(y: int, m: int, d: int) -> dt.date:
    return _jdn_to_greg(_hijri_to_jdn(y, m, d))


def holidays(start: dt.date, end: dt.date) -> list[dict]:
    """Occasions between start and end (inclusive), sorted by date."""
    out = []
    for year in range(start.year, end.year + 1):
        for m, d, name, occ, code in FIXED:
            day = dt.date(year, m, d)
            out.append(
                {
                    "date": day,
                    "title": name,
                    "occasion": occ,
                    "dress_code": code,
                    "kind": "holiday",
                    "approximate": False,
                }
            )
    for hy in range(_greg_to_hijri_year(start) - 1, _greg_to_hijri_year(end) + 2):
        for m, d, name, occ, code, n in ISLAMIC:
            first = hijri_to_gregorian(hy, m, d)
            for k in range(n):
                out.append(
                    {
                        "date": first + dt.timedelta(days=k),
                        "title": name + (f" (day {k + 1})" if n > 1 else ""),
                        "occasion": occ,
                        "dress_code": code,
                        "kind": "holiday",
                        "approximate": True,
                    }
                )
    return sorted((h for h in out if start <= h["date"] <= end), key=lambda h: h["date"])


def season_of(day: dt.date) -> list[dict]:
    out = []
    for name, m1, d1, m2, d2, occ, code in SEASONS:
        if dt.date(day.year, m1, d1) <= day <= dt.date(day.year, m2, d2):
            out.append({"title": name, "occasion": occ, "dress_code": code})
    return out
