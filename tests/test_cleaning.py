import numpy as np
import pandas as pd
import pytest

from assignment_streamlit_app import cleaning
from tests.conftest import NaN, make_raw


def _row(df, vehicle, start):
    match = df[(df["vehicle_id"] == vehicle) & (
        df["started_time"] == pd.Timestamp(start))]
    assert len(match) == 1
    return match.iloc[0]


def test_deduplicate_keeps_uncharged_row_per_vehicle():
    raw = make_raw(
        [
            ("A", "2023-01-02 08:00", "2023-01-02 08:30", 80, 60, True, False),
            ("A", "2023-01-02 08:00", "2023-01-02 08:30", 80, 60, False, False),
            ("A", "2023-01-02 08:00", "2023-01-02 08:30", 80, 60, False, False),
            # same start time on another vehicle is a different event
            ("B", "2023-01-02 08:00", "2023-01-02 08:30", 70, 60, True, False),
        ]
    )
    out = cleaning.deduplicate(raw)
    assert len(out) == 2
    assert not bool(_row(out, "A", "2023-01-02 08:00")["charged"])
    assert bool(_row(out, "B", "2023-01-02 08:00")["charged"])


def test_drop_incomplete_rules():
    raw = make_raw(
        [
            ("A", "2023-01-02 08:00", "2023-01-02 08:30", 80, 60, False, False),  # keep
            ("A", "2023-01-02 09:00", "2023-01-02 09:30", NaN, 60, False, False),  # drop
            ("A", "2023-01-02 10:00", "2023-01-02 10:30",
             NaN, 60, True, True),  # keep (agent)
            ("A", "2023-01-02 11:00", "2023-01-02 11:30",
             80, NaN, False, False),  # no end level
            ("A", "2023-01-02 12:00", "2023-01-02 12:30",
             80, 60, None, False),  # no charged flag
            ("A", "2023-01-02 13:00", "2023-01-02 13:30",
             80, 60, False, None),  # no service flag
        ]
    )
    out = cleaning.drop_incomplete(raw)
    assert out["started_time"].dt.hour.tolist() == [8, 10]


def test_rental_type_labels(raw_events):
    out = cleaning.add_rental_type(raw_events)
    assert out["rental_type"].tolist()[:4] == [
        "customer_rental",
        "agent_charge",
        "agent_move",
        "customer_rental",
    ]


def test_duration_rounds_half_away_from_zero():
    raw = make_raw(
        [
            ("A", "2023-01-02 08:00:00", "2023-01-02 08:02:30", 80, 60, False, False),
            ("A", "2023-01-02 09:00:00", "2023-01-02 09:00:29", 80, 60, False, False),
        ]
    )
    assert cleaning.add_duration(raw)["duration"].tolist() == [3, 0]


def test_energy_consumed_only_for_customers(raw_events):
    out = cleaning.add_energy_consumed(cleaning.add_rental_type(raw_events))
    assert out.loc[0, "energy_consumed"] == 20
    assert np.isnan(out.loc[1, "energy_consumed"])


@pytest.fixture
def dataset(raw_events):
    return cleaning.build_rental_dataset(raw_events)


@pytest.mark.parametrize(
    ("vehicle", "start", "expected"),
    [
        ("A", "2023-01-02 08:00", 80),  # customer: own start level
        ("A", "2023-01-02 09:00", 60),  # charge: previous end level
        ("A", "2023-01-02 11:00", 95),  # move right after a charge: own end level
        ("B", "2023-01-02 07:00", NaN),  # agent event without history
        ("B", "2023-01-02 08:00", 30),  # move after a customer: previous end level
        ("B", "2023-01-02 09:00", 30),  # charge after a move: previous end level
    ],
)
def test_fill_charge_level_start(dataset, vehicle, start, expected):
    value = _row(dataset, vehicle, start)["chargelevelstart_filled"]
    if np.isnan(expected):
        assert np.isnan(value)
    else:
        assert value == expected


def test_charge_session_metrics(dataset):
    a = _row(dataset, "A", "2023-01-02 09:00")
    assert (a["charge_level_end_fixed"], a["energy_charged"], a["charged_duration"]) == (
        95,
        35,
        120,
    )
    b = _row(dataset, "B", "2023-01-02 09:00")
    assert (b["charge_level_end_fixed"], b["energy_charged"], b["charged_duration"]) == (
        70,
        40,
        1480,
    )


def test_last_charge_has_no_session_metrics(dataset):
    last = _row(dataset, "B", "2023-01-03 12:00")
    assert last[["charge_level_end_fixed",
                 "energy_charged", "charged_duration"]].isna().all()


def test_session_metrics_empty_for_non_charges(dataset):
    others = dataset[dataset["rental_type"] != "agent_charge"]
    assert others["charge_level_end_fixed"].isna().all()


def test_pipeline_is_independent_of_input_order(raw_events):
    shuffled = raw_events.sample(frac=1, random_state=0)
    pd.testing.assert_frame_equal(cleaning.build_rental_dataset(
        raw_events), cleaning.build_rental_dataset(shuffled))


def test_pipeline_does_not_modify_input(raw_events):
    before = raw_events.copy()
    cleaning.build_rental_dataset(raw_events)
    pd.testing.assert_frame_equal(raw_events, before)
