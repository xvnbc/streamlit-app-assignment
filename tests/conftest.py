import numpy as np
import pandas as pd
import pytest

from assignment_streamlit_app.loading import coerce_types

NaN = np.nan

# vehicle, start, end, level_start, level_end, charged, servicerental
EVENTS = [
    # Vehicle A: customer -> charge -> move (right after charge) -> customer
    ("A", "2023-01-02 08:00", "2023-01-02 08:30", 80, 60, False, False),
    ("A", "2023-01-02 09:00", "2023-01-02 09:10", NaN, 55, True, True),
    ("A", "2023-01-02 11:00", "2023-01-02 11:05", NaN, 95, False, True),
    ("A", "2023-01-02 11:30", "2023-01-02 12:00", 94, 80, False, False),
    # Vehicle B: move first -> customer -> move -> charge -> customer -> last charge
    ("B", "2023-01-02 07:00", "2023-01-02 07:10", NaN, 50, False, True),
    ("B", "2023-01-02 07:30", "2023-01-02 07:50", 50, 30, False, False),
    ("B", "2023-01-02 08:00", "2023-01-02 08:10", NaN, 30, False, True),
    ("B", "2023-01-02 09:00", "2023-01-02 09:05", NaN, 40, True, True),
    ("B", "2023-01-03 09:40", "2023-01-03 10:00", 70, 65, False, False),
    ("B", "2023-01-03 12:00", "2023-01-03 12:05", NaN, 66, True, True),
]


def make_raw(rows) -> pd.DataFrame:
    df = pd.DataFrame(
        rows,
        columns=[
            "vehicle_id",
            "started_time",
            "finished_time",
            "chargelevelstart",
            "chargelevelend",
            "charged",
            "servicerental",
        ],
    )
    df.insert(1, "model_id", "M1")
    return coerce_types(df)


@pytest.fixture
def raw_events() -> pd.DataFrame:
    return make_raw(EVENTS)
