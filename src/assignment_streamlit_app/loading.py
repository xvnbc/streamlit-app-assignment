"""Reading the raw event file into a typed DataFrame."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config as c

_TRUE_VALUES = {"true", "t", "1", "yes"}
_FALSE_VALUES = {"false", "f", "0", "no"}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case column names and map known aliases to canonical names."""
    renamed = {col: col.strip().lower() for col in df.columns}
    out = df.rename(columns=renamed)
    return out.rename(columns=c.COLUMN_ALIASES)


def parse_bool(series: pd.Series) -> pd.Series:
    """Convert True/False-like values to a nullable boolean series.

    Unrecognised values and missing values become <NA>.
    """
    if pd.api.types.is_bool_dtype(series):
        return series.astype("boolean")
    text = series.astype("string").str.strip().str.lower()
    result = pd.Series(pd.NA, index=series.index, dtype="boolean")
    result[text.isin(_TRUE_VALUES).fillna(False)] = True
    result[text.isin(_FALSE_VALUES).fillna(False)] = False
    return result


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Give every raw column its expected dtype."""
    missing = set(c.RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df[c.RAW_COLUMNS].copy()
    out[c.VEHICLE_ID] = out[c.VEHICLE_ID].astype("string")
    out[c.MODEL_ID] = out[c.MODEL_ID].astype("string")
    for col in (c.STARTED_TIME, c.FINISHED_TIME):
        out[col] = pd.to_datetime(out[col], format="ISO8601", errors="coerce")
    for col in (c.CHARGE_START, c.CHARGE_END):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    for col in (c.CHARGED, c.SERVICE_RENTAL):
        out[col] = parse_bool(out[col])
    return out


def load_raw_data(path: str | Path) -> pd.DataFrame:
    """Read the raw CSV and return it with canonical names and dtypes."""
    df = pd.read_csv(path)
    return coerce_types(normalize_columns(df))
