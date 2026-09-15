"""
GridPilot AI — Dutch Calendar & Holiday Reference (2024)
=========================================================
Official Dutch national public holidays for the 2024 calendar year,
matching DSO Liander service territory electricity demand profiles.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional, Set

DUTCH_HOLIDAYS_2024: Dict[str, str] = {
    "2024-01-01": "Nieuwjaarsdag (New Year's Day)",
    "2024-03-29": "Goede Vrijdag (Good Friday)",
    "2024-03-31": "Eerste Paasdag (Easter Sunday)",
    "2024-04-01": "Tweede Paasdag (Easter Monday)",
    "2024-04-27": "Koningsdag (King's Day)",
    "2024-05-05": "Bevrijdingsdag (Liberation Day)",
    "2024-05-09": "Hemelvaartsdag (Ascension Day)",
    "2024-05-19": "Eerste Pinksterdag (Whit Sunday)",
    "2024-05-20": "Tweede Pinksterdag (Whit Monday)",
    "2024-12-25": "Eerste Kerstdag (Christmas Day)",
    "2024-12-26": "Tweede Kerstdag (Boxing Day)",
}

DUTCH_HOLIDAY_DATES_2024: Set[str] = set(DUTCH_HOLIDAYS_2024.keys())


def is_dutch_holiday(dt: datetime | date | str) -> bool:
    """
    Check if a given date or timestamp falls on a Dutch public holiday.

    Parameters
    ----------
    dt : datetime | date | str
        Date, datetime, or ISO string (e.g. "2024-04-27").

    Returns
    -------
    bool
        True if the date is an official Dutch public holiday.
    """
    if isinstance(dt, str):
        date_str = dt[:10]
    elif isinstance(dt, datetime):
        date_str = dt.strftime("%Y-%m-%d")
    elif isinstance(dt, date):
        date_str = dt.isoformat()
    else:
        date_str = str(dt)[:10]

    return date_str in DUTCH_HOLIDAY_DATES_2024


def get_holiday_name(dt: datetime | date | str) -> Optional[str]:
    """Return holiday name or None if not a holiday."""
    if isinstance(dt, str):
        date_str = dt[:10]
    elif isinstance(dt, datetime):
        date_str = dt.strftime("%Y-%m-%d")
    elif isinstance(dt, date):
        date_str = dt.isoformat()
    else:
        date_str = str(dt)[:10]

    return DUTCH_HOLIDAYS_2024.get(date_str)
