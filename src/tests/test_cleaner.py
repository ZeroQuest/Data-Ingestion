import pandas as pd
import pytest

from cleaners.cleaners import (
    normalize_columns,
    normalize_for_database
)

def test_normalize_columns_strips_whitespace():
    df = pd.DataFrame(columns=[" station ", " date "])

    result = normalize_columns(df)

    assert list(result.columns) == ["station", "date"]

def test_normalize_columns_lowercase():
    df = pd.DataFrame(columns=["STATION", "DATE"])

    result = normalize_columns(df)

    assert list(result.columns) == ["station", "date"]

def test_normalize_columns_replace_space():
    df = pd.DataFrame(columns=["Station Name", "Date Recorded"])

    result = normalize_columns(df)

    assert list(result.columns) == ["station_name", "date_recorded"]

def test_normalize_columns_all_transforms():
    df = pd.DataFrame(columns=[" Station ", "Date Recorded"])

    result = normalize_columns(df)

    assert list(result.columns) == [
        "station",
        "date_recorded"
    ]

def test_normalize_database_pdna_to_none():
    df = pd.DataFrame({"station": ["ABC", pd.NA]})

    result = normalize_for_database(df)

    assert result.loc[1, "station"] is None

def test_normalize_database_nan_to_none():
    df = pd.DataFrame({"temperature": [10.0, float("nan")]})

    result = normalize_for_database(df)

    assert result.loc[1, "temperature"] is None

def test_normalize_database_valid():
    df = pd.DataFrame({"station": ["ABC"], "temperature": [25.5]})

    result = normalize_for_database(df)

    assert result.loc[0, "station"] == "ABC"
    assert result.loc[0, "temperature"] == 25.5

def test_normalize_database_dtype():
    df = pd.DataFrame({"station": ["ABC"]})

    result = normalize_for_database(df)

    assert result["station"].dtype == object
