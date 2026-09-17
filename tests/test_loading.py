import pandas as pd
import pytest

from assignment_streamlit_app.loading import (
    load_raw_data,
    normalize_columns,
    parse_bool,
)

HEADER = (
    "VEHICLE_ID,MODEL_ID,STARTEDTIME,FINISHED_TIME,"
    "CHARGELEVELSTART,CHARGELEVELEND,CHARGED,SERVICERENTAL"
)
CSV = (
    HEADER
    + """
v1,m1,2023-01-01 12:14:45.99,2023-01-01 12:40:00,80,70,False,False
v1,m1,2023-01-01 13:00:00,2023-01-01 13:10:00,,71,true,TRUE
v2,m1,not a date,2023-01-01 13:10:00,abc,50,,maybe
"""
)


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "rentals.csv"
    path.write_text(CSV)
    return path


def test_normalize_columns_maps_aliases():
    df = pd.DataFrame(columns=["VEHICLE_ID", " StartedTime ", "FINISHED_TIME"])
    assert list(normalize_columns(df).columns) == [
        "vehicle_id", "started_time", "finished_time"]


def test_parse_bool_handles_text_and_unknowns():
    s = pd.Series(["True", "false", "TRUE", "1", "0", None, "maybe"])
    assert parse_bool(s).tolist() == [True, False, True, True, False, pd.NA, pd.NA]


def test_parse_bool_keeps_real_booleans():
    assert parse_bool(pd.Series([True, False])).tolist() == [True, False]


def test_load_raw_data_types(csv_path):
    df = load_raw_data(csv_path)
    assert len(df) == 3
    assert pd.api.types.is_datetime64_any_dtype(df["started_time"])
    assert df["chargelevelstart"].dtype == "float64"
    assert df.loc[0, "started_time"] == pd.Timestamp("2023-01-01 12:14:45.990")
    assert df["charged"].tolist()[:2] == [False, True]


def test_load_raw_data_bad_values_become_missing(csv_path):
    row = load_raw_data(csv_path).iloc[2]
    assert pd.isna(row["started_time"])
    assert pd.isna(row["chargelevelstart"])
    assert pd.isna(row["charged"])
    assert pd.isna(row["servicerental"])


def test_missing_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("vehicle_id,model_id\nv1,m1\n")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_raw_data(path)
