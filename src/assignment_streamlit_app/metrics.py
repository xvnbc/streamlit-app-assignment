"""Fleet-level indicators and aggregations used by the dashboard."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as c

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def customer_rentals(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["rental_type"] == c.CUSTOMER_RENTAL]


@dataclass(frozen=True)
class UtilizationSummary:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    n_days: int
    n_vehicles: int
    n_rentals: int
    avg_duration_min: float
    rentals_per_vehicle_per_day: float
    utilization_rate: float


def utilization_summary(df: pd.DataFrame) -> UtilizationSummary:
    """Headline usage figures computed on customer rentals.

    utilization rate = total rented hours / (number of vehicles * hours in period),
    where the period runs from the first rental start to the last rental end
    (both days included).
    """
    cust = customer_rentals(df)
    if cust.empty:
        raise ValueError("No customer rentals in the data.")

    start = cust[c.STARTED_TIME].min().normalize()
    end = cust[c.FINISHED_TIME].max().normalize()
    n_days = (end - start).days + 1
    n_vehicles = cust[c.VEHICLE_ID].nunique()
    rented_hours = cust["duration"].sum() / 60
    per_vehicle = rentals_per_vehicle(df, n_days)

    return UtilizationSummary(
        start_date=start,
        end_date=end,
        n_days=n_days,
        n_vehicles=n_vehicles,
        n_rentals=len(cust),
        avg_duration_min=float(cust["duration"].mean()),
        rentals_per_vehicle_per_day=float(per_vehicle["rentals_per_day"].mean()),
        utilization_rate=float(rented_hours / (n_vehicles * n_days * 24)),
    )


def rentals_per_vehicle(df: pd.DataFrame, n_days: int) -> pd.DataFrame:
    """Customer rental count and daily rate for each vehicle, busiest first."""
    counts = (
        customer_rentals(df)
        .groupby(c.VEHICLE_ID)
        .size()
        .reset_index(name="rentals_count")
        .sort_values("rentals_count", ascending=False, ignore_index=True)
    )
    counts["rentals_per_day"] = counts["rentals_count"] / n_days
    return counts


def event_type_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Number and share of events per rental type."""
    counts = (
        df["rental_type"]
        .value_counts()
        .reindex(c.RENTAL_TYPES, fill_value=0)
        .rename_axis("rental_type")
        .reset_index(name="count")
    )
    counts["share"] = counts["count"] / counts["count"].sum()
    return counts


def monthly_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Customer rentals and total rented minutes per calendar month."""
    cust = customer_rentals(df)
    month = cust[c.STARTED_TIME].dt.to_period("M").dt.to_timestamp()
    return (
        cust.groupby(month)
        .agg(rentals=("duration", "size"), total_duration_min=("duration", "sum"))
        .rename_axis("month")
        .reset_index()
    )


def weekday_demand(df: pd.DataFrame) -> pd.DataFrame:
    """Customer rentals and total rented minutes per day of week (Monday first)."""
    cust = customer_rentals(df)
    weekday = cust[c.STARTED_TIME].dt.dayofweek
    out = (
        cust.groupby(weekday)
        .agg(rentals=("duration", "size"), total_duration_min=("duration", "sum"))
        .reindex(range(7), fill_value=0)
        .rename_axis("weekday_num")
        .reset_index()
    )
    out["weekday"] = [WEEKDAY_NAMES[i] for i in out["weekday_num"]]
    return out


def hourly_profile(df: pd.DataFrame, bin_minutes: int = 30) -> pd.DataFrame:
    """Event starts per time-of-day bin, split by rental type.

    `hour` is the bin start expressed in hours (e.g. 7.5 for 07:30).
    """
    if bin_minutes <= 0 or 1440 % bin_minutes:
        raise ValueError("bin_minutes must be a positive divisor of 1440.")
    t = df[c.STARTED_TIME]
    minute_of_day = t.dt.hour * 60 + t.dt.minute
    bins = (minute_of_day // bin_minutes) * bin_minutes / 60
    counts = df.groupby([df["rental_type"], bins.rename("hour")]).size().unstack(fill_value=0)
    all_bins = np.arange(0, 24, bin_minutes / 60)
    counts = counts.reindex(index=c.RENTAL_TYPES, columns=all_bins, fill_value=0)
    return counts.stack().rename("count").reset_index()


def battery_distribution(
    df: pd.DataFrame,
    rental_type: str,
    column: str,
    bin_width: int = c.DEFAULT_SOC_BIN_WIDTH,
) -> pd.DataFrame:
    """Share of events of one type falling in each battery-level bin.

    Typical uses: start level of customer rentals (`chargelevelstart`), start and end
    level of charges (`chargelevelstart_filled`, `charge_level_end_fixed`), start level
    of moves (`chargelevelstart_filled`).
    """
    values = df.loc[df["rental_type"] == rental_type, column].dropna()
    values = values.clip(0, 100)
    bins = (values // bin_width) * bin_width
    all_bins = np.arange(0, 100 + bin_width, bin_width, dtype=float)
    counts = bins.value_counts().reindex(all_bins, fill_value=0).sort_index()
    total = counts.sum()
    out = counts.rename_axis("battery_bin").reset_index(name="count")
    out["share"] = out["count"] / total if total else 0.0
    return out


@dataclass(frozen=True)
class ChargingSummary:
    n_sessions: int
    full_ratio: float
    avg_rate_pct_per_min: float


def valid_charge_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Charging sessions with a positive duration and positive energy added."""
    charges = df[df["rental_type"] == c.AGENT_CHARGE]
    return charges[(charges["charged_duration"] > 0) & (charges["energy_charged"] > 0)]


def charging_summary(df: pd.DataFrame) -> ChargingSummary:
    """Share of sessions reaching 100 % and average charging speed.

    The speed is averaged over sessions ending below 100 %, since a full battery
    may have stayed plugged in after finishing, which would bias the rate down.
    """
    charges = valid_charge_sessions(df)
    n = len(charges)
    if n == 0:
        return ChargingSummary(0, float("nan"), float("nan"))
    full_ratio = (charges["charge_level_end_fixed"] >= 100).mean()
    non_full = charges[charges["charge_level_end_fixed"] < 100]
    rate = (non_full["energy_charged"] / non_full["charged_duration"]).mean()
    return ChargingSummary(n, float(full_ratio), float(rate))
