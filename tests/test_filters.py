import datetime as dt

import pytest

from assignment_streamlit_app.cleaning import build_rental_dataset
from assignment_streamlit_app.filters import (
    apply_filters,
    filter_by_date_range,
    filter_by_rental_types,
    filter_by_vehicles,
)


@pytest.fixture
def dataset(raw_events):
    return build_rental_dataset(raw_events)


def test_date_range_is_inclusive(dataset):
    day2 = dt.date(2023, 1, 2)
    assert len(filter_by_date_range(dataset, day2, day2)) == 8
    assert len(filter_by_date_range(dataset, start=dt.date(2023, 1, 3))) == 2
    assert len(filter_by_date_range(dataset)) == len(dataset)


def test_date_range_rejects_reversed_bounds(dataset):
    with pytest.raises(ValueError):
        filter_by_date_range(dataset, dt.date(2023, 1, 3), dt.date(2023, 1, 2))


def test_rental_type_filter(dataset):
    out = filter_by_rental_types(dataset, ["agent_charge"])
    assert set(out["rental_type"]) == {"agent_charge"}
    assert filter_by_rental_types(dataset, None) is dataset
    assert filter_by_rental_types(dataset, []).empty


def test_rental_type_filter_rejects_unknown(dataset):
    with pytest.raises(ValueError):
        filter_by_rental_types(dataset, ["taxi"])


def test_vehicle_filter(dataset):
    assert set(filter_by_vehicles(dataset, ["A"])["vehicle_id"]) == {"A"}
    assert len(filter_by_vehicles(dataset, [])) == len(dataset)
    assert filter_by_vehicles(dataset, ["Z"]).empty


def test_apply_filters_combines(dataset):
    out = apply_filters(
        dataset,
        start=dt.date(2023, 1, 2),
        end=dt.date(2023, 1, 2),
        rental_types=["customer_rental"],
        vehicle_ids=["B"],
    )
    assert len(out) == 1
