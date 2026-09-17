"""Battery threshold analysis: how likely is a vehicle to be rented soon after charging?"""

from __future__ import annotations

import pandas as pd

from . import config as c


def build_charge_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """One row per agent charge that has a following event.

    Columns added:
        soc               battery level when the charge ended
        next_type         type of the vehicle's next event
        label_rented      1 if that next event is a customer rental
        time_to_next_min  minutes between the charge event's end and the next start
    """
    df = df.sort_values([c.VEHICLE_ID, c.STARTED_TIME], kind="stable")
    by_vehicle = df.groupby(c.VEHICLE_ID, sort=False)
    df = df.assign(
        next_type=by_vehicle["rental_type"].shift(-1),
        next_started_time=by_vehicle[c.STARTED_TIME].shift(-1),
    )
    snap = df[
        (df["rental_type"] == c.AGENT_CHARGE)
        & (df["charge_level_end_fixed"] >= 0)
        & df["next_type"].notna()
    ].copy()
    snap["soc"] = snap["charge_level_end_fixed"]
    snap["label_rented"] = (snap["next_type"] == c.CUSTOMER_RENTAL).astype(int)
    snap["time_to_next_min"] = (
        snap["next_started_time"] - snap[c.FINISHED_TIME]
    ).dt.total_seconds() / 60
    return snap.reset_index(drop=True)


def rental_probability_by_soc(
    snapshots: pd.DataFrame,
    window_minutes: float = c.DEFAULT_WINDOW_MINUTES,
    bin_width: int = c.DEFAULT_SOC_BIN_WIDTH,
) -> pd.DataFrame:
    """Share of charges followed by a customer rental, per battery-level bin.

    Only charges whose next event starts within `window_minutes` are counted,
    so the probability reads: "given the vehicle is used again within the window,
    how often is it by a customer?".
    """
    if window_minutes <= 0:
        raise ValueError("window_minutes must be positive.")
    if bin_width <= 0:
        raise ValueError("bin_width must be positive.")
    within = snapshots[snapshots["time_to_next_min"] <= window_minutes]
    soc_bin = ((within["soc"] // bin_width) * bin_width).rename("soc_bin")
    return (
        within.groupby(soc_bin)["label_rented"]
        .agg(prob_rented="mean", n_events="size")
        .reset_index()
    )
