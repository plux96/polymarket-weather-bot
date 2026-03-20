"""
Smart Entry Timing for Weather Trades

Weather models become MORE accurate as we get closer to the resolution time.
Trading 6-12 hours before resolution gives the biggest edge because forecast
ensemble spread narrows significantly in the final hours.

Timing score tiers:
    0-6 hours   -> 1.5  (models ~95% accurate, optimal window)
    6-12 hours  -> 1.3  (models ~90% accurate, good window)
    12-24 hours -> 1.0  (normal)
    24-48 hours -> 0.8  (models less certain)
    48+ hours   -> 0.5  (high uncertainty, reduce bets)
"""

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Timing tiers: (max_hours, timing_score, phase_name, confidence_boost)
# Ordered from tightest window to widest so we can match the first bucket
# whose upper bound exceeds hours_to_resolution.
# ---------------------------------------------------------------------------
TIMING_TIERS = [
    (6,  1.5, "optimal",  1.3),
    (12, 1.3, "good",     1.2),
    (24, 1.0, "normal",   1.0),
    (48, 0.8, "early",    0.8),
]

# Fallback for anything beyond 48 hours
DEFAULT_TIER = (None, 0.5, "speculative", 0.6)

# Safety cap so a single bet never exceeds this dollar amount
MAX_BET = 50.0


def _parse_resolution_dt(market_date: str, market_end_time: str) -> datetime:
    """Build a timezone-aware UTC datetime from a date string and time string.

    Accepted formats
    ----------------
    market_date     : "YYYY-MM-DD"
    market_end_time : "HH:MM" or "HH:MM:SS"  (assumed UTC)
    """
    time_parts = market_end_time.strip().split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
    second = int(time_parts[2]) if len(time_parts) > 2 else 0

    date_parts = market_date.strip().split("-")
    year = int(date_parts[0])
    month = int(date_parts[1])
    day = int(date_parts[2])

    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _hours_until(resolution_dt: datetime) -> float:
    """Return hours from now (UTC) until *resolution_dt*."""
    now = datetime.now(timezone.utc)
    delta = resolution_dt - now
    return delta.total_seconds() / 3600.0


def _tier_for_hours(hours: float) -> tuple:
    """Return the matching timing tier tuple for the given hours-out value."""
    if hours < 0:
        # Market already resolved
        return (None, 0.0, "expired", 0.0)
    for max_h, score, phase, boost in TIMING_TIERS:
        if hours <= max_h:
            return (max_h, score, phase, boost)
    return DEFAULT_TIER


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_timing_score(market_date: str, market_end_time: str) -> dict:
    """Compute timing metrics for a market that resolves at the given date/time.

    Parameters
    ----------
    market_date : str
        Resolution date in ``"YYYY-MM-DD"`` format.
    market_end_time : str
        Resolution time (UTC) in ``"HH:MM"`` or ``"HH:MM:SS"`` format.

    Returns
    -------
    dict
        {
            "timing_score": float,
            "hours_to_resolution": float,
            "phase": str,
            "confidence_boost": float,
        }
    """
    resolution_dt = _parse_resolution_dt(market_date, market_end_time)
    hours = _hours_until(resolution_dt)
    _, score, phase, boost = _tier_for_hours(hours)

    return {
        "timing_score": score,
        "hours_to_resolution": round(hours, 2),
        "phase": phase,
        "confidence_boost": boost,
    }


def adjust_bet_for_timing(base_bet: float, timing: dict, max_bet: float = MAX_BET) -> float:
    """Scale *base_bet* by the timing score, capped at *max_bet*.

    Parameters
    ----------
    base_bet : float
        The unadjusted bet size in dollars.
    timing : dict
        Output of :func:`get_timing_score`.
    max_bet : float, optional
        Hard ceiling for any single bet (default ``50.0``).

    Returns
    -------
    float
        Adjusted bet size, rounded to two decimal places.
    """
    adjusted = base_bet * timing["timing_score"]
    return round(min(adjusted, max_bet), 2)


def get_optimal_markets(markets: list) -> list:
    """Filter and rank markets by timing, prioritising 0-12 hours from resolution.

    Each market dict is expected to contain at least::

        {
            "market_date": "YYYY-MM-DD",
            "market_end_time": "HH:MM",
            ...
        }

    Parameters
    ----------
    markets : list[dict]
        List of market dictionaries.

    Returns
    -------
    list[dict]
        Subset of *markets* that have not yet expired, sorted best-timing-first.
        Each dict gets three extra keys: ``timing_score``, ``hours_to_resolution``,
        and ``phase``.
    """
    scored: list[dict] = []

    for market in markets:
        timing = get_timing_score(market["market_date"], market["market_end_time"])

        # Skip expired markets
        if timing["phase"] == "expired":
            continue

        enriched = {**market, **timing}
        scored.append(enriched)

    # Primary sort: higher timing_score first; secondary: fewer hours out first
    scored.sort(key=lambda m: (-m["timing_score"], m["hours_to_resolution"]))
    return scored
