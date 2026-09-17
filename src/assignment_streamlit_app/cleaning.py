"""Cleaning and feature engineering (Python port of the original SQL pipeline).

Pipeline, in order:
    deduplicate -> drop_incomplete -> add_rental_type -> add_duration
    -> add_energy_consumed -> fill_charge_level_start -> add_charge_session_metrics

`build_rental_dataset` runs all steps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as c


def _round_half_away(values: pd.Series) -> pd.Series:
    """Round like SQL ROUND(x, 0): halves go away from zero (pandas rounds to even)."""
    return np.sign(values) * np.floor(np.abs(values) + 0.5)


def _minutes_between(start: pd.Series, end: pd.Series) -> pd.Series:
    return _round_half_away((end - start).dt.total_seconds() / 60)


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicates, then keep one row per (vehicle, start time).

    When a vehicle has several rows with the same start time, the row with
    charged == False is kept.
    """
    out = df.drop_duplicates()
    out = out.sort_values(
        [c.VEHICLE_ID, c.STARTED_TIME, c.CHARGED], na_position="last", kind="stable"
    )
    out = out.drop_duplicates(subset=[c.VEHICLE_ID, c.STARTED_TIME], keep="first")
    return out.reset_index(drop=True)


def drop_incomplete(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that cannot be used.

    Kept rows have a vehicle, a start time, known charged / servicerental flags
    and an end battery level. A missing start battery level is allowed only for
    agent events, because it is imputed later from the previous event.
    """
    has_start_level = df[c.CHARGE_START].notna()
    is_agent = df[c.SERVICE_RENTAL].fillna(False).astype(bool)
    mask = (
        df[c.VEHICLE_ID].notna()
        & df[c.STARTED_TIME].notna()
        & df[c.CHARGED].notna()
        & df[c.SERVICE_RENTAL].notna()
        & df[c.CHARGE_END].notna()
        & (has_start_level | is_agent)
    )
    return df.loc[mask].reset_index(drop=True)


def add_rental_type(df: pd.DataFrame) -> pd.DataFrame:
    """Label each event as customer_rental, agent_charge or agent_move."""
    out = df.copy()
    service = out[c.SERVICE_RENTAL].astype(bool)
    charged = out[c.CHARGED].astype(bool)
    out["rental_type"] = np.select(
        [~service, service & charged],
        [c.CUSTOMER_RENTAL, c.AGENT_CHARGE],
        default=c.AGENT_MOVE,
    )
    return out


def add_duration(df: pd.DataFrame) -> pd.DataFrame:
    """Event duration in whole minutes."""
    out = df.copy()
    out["duration"] = _minutes_between(out[c.STARTED_TIME], out[c.FINISHED_TIME])
    return out


def add_energy_consumed(df: pd.DataFrame) -> pd.DataFrame:
    """Battery points used during customer rentals (NaN for agent events)."""
    out = df.copy()
    consumed = out[c.CHARGE_START] - out[c.CHARGE_END]
    out["energy_consumed"] = consumed.where(out["rental_type"] == c.CUSTOMER_RENTAL)
    return out


def sort_events(df: pd.DataFrame) -> pd.DataFrame:
    """Order events chronologically within each vehicle."""
    return df.sort_values([c.VEHICLE_ID, c.STARTED_TIME], kind="stable").reset_index(drop=True)


def fill_charge_level_start(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct the battery level at the start of each event.

    - customer rental: its own recorded start level
    - agent charge: end level of the vehicle's previous event
    - agent move after anything but a charge: end level of the previous event
    - agent move right after a charge: its own end level (a move barely uses energy,
      and the previous charge's end level is not recorded)
    - an agent event with no previous event stays NaN
    """
    out = sort_events(df)
    by_vehicle = out.groupby(c.VEHICLE_ID, sort=False)
    prev_type = by_vehicle["rental_type"].shift(1)
    prev_end = by_vehicle[c.CHARGE_END].shift(1)

    rental_type = out["rental_type"]
    is_move = rental_type == c.AGENT_MOVE
    out["chargelevelstart_filled"] = np.select(
        [
            rental_type == c.CUSTOMER_RENTAL,
            rental_type == c.AGENT_CHARGE,
            is_move & prev_type.notna() & (prev_type != c.AGENT_CHARGE),
            is_move & (prev_type == c.AGENT_CHARGE),
        ],
        [out[c.CHARGE_START], prev_end, prev_end, out[c.CHARGE_END]],
        default=np.nan,
    )
    return out


def add_charge_session_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """For agent charges, derive end level, energy added and plugged-in time.

    The end of a charging session is not recorded, so it is taken from the
    vehicle's next event: its reconstructed start level and its start time.
    Requires `fill_charge_level_start` to have run.
    """
    out = sort_events(df)
    by_vehicle = out.groupby(c.VEHICLE_ID, sort=False)
    next_start_level = by_vehicle["chargelevelstart_filled"].shift(-1)
    next_start_time = by_vehicle[c.STARTED_TIME].shift(-1)

    is_charge = out["rental_type"] == c.AGENT_CHARGE
    out["charge_level_end_fixed"] = next_start_level.where(is_charge)
    out["energy_charged"] = (next_start_level - out["chargelevelstart_filled"]).where(is_charge)
    out["charged_duration"] = _minutes_between(out[c.STARTED_TIME], next_start_time).where(
        is_charge
    )
    return out


def build_rental_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    """Run the full cleaning pipeline on a typed raw DataFrame."""
    df = deduplicate(raw)
    df = drop_incomplete(df)
    df = add_rental_type(df)
    df = add_duration(df)
    df = add_energy_consumed(df)
    df = fill_charge_level_start(df)
    df = add_charge_session_metrics(df)
    return df
