"""Prices of the game in credits, and how they move with time. Any price that is set in the game's year 700 (a ship's
PRICE_AT_700, a supply's unit price) is brought to the date it is paid with `at_date`.

Inflation is the same for every price, compounded each year from the start of the year 700. The 1% a year is a rate for
the whole game, so a price at year 765 is about 2.1 times its year 700 value.
"""

from __future__ import annotations
from datetime import datetime

INFLATION: float = 0.01  # per year, compounded from PRICE_BASE
PRICE_BASE: datetime = datetime(700, 1, 1)  # the date the prices are set at
SECONDS_PER_YEAR: float = 365.2425 * 24 * 60 * 60


def at_date(price: float, when: datetime) -> float:
    """What `price`, set at PRICE_BASE, is worth at `when`, credits."""
    years: float = (when - PRICE_BASE).total_seconds() / SECONDS_PER_YEAR
    return price * (1 + INFLATION) ** years
