"""Row filters driven by the dashboard's sidebar controls."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

import pandas as pd

from . import config as c


def filter_by_date_range(
    df: pd.DataFrame, start: dt.date | None = None, end: dt.date | None = None
) -> pd.DataFrame:
    """Keep events that start on a day between `start` and `end`, both included."""
    if start is not None and end is not None and start > end:
        raise ValueError("start must not be after end.")
    day = df[c.STARTED_TIME].dt.normalize()
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= day >= pd.Timestamp(start)
    if end is not None:
        mask &= day <= pd.Timestamp(end)
    return df[mask]


def filter_by_rental_types(df: pd.DataFrame, types: Iterable[str] | None) -> pd.DataFrame:
    """Keep the given event types; None keeps everything."""
    if types is None:
        return df
    types = list(types)
    unknown = set(types) - set(c.RENTAL_TYPES)
    if unknown:
        raise ValueError(f"Unknown rental types: {sorted(unknown)}")
    return df[df["rental_type"].isin(types)]


def filter_by_vehicles(df: pd.DataFrame, vehicle_ids: Iterable[str] | None) -> pd.DataFrame:
    """Keep the given vehicles; None or an empty selection keeps everything."""
    if not vehicle_ids:
        return df
    return df[df[c.VEHICLE_ID].isin(list(vehicle_ids))]


def apply_filters(
    df: pd.DataFrame,
    start: dt.date | None = None,
    end: dt.date | None = None,
    rental_types: Iterable[str] | None = None,
    vehicle_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Apply all sidebar filters at once."""
    out = filter_by_date_range(df, start, end)
    out = filter_by_rental_types(out, rental_types)
    return filter_by_vehicles(out, vehicle_ids)
