import pandas as pd
import logging

logger = logging.getLogger(__name__)


def normalize_columns(df):
    """
    Normalizes the data for entry into sql
    """
    df = df.copy()
    original_data = df.columns.tolist()
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.lower()
    df.columns = df.columns.str.replace(" ", "_")
    logger.info(f"Normalized columns: {original_data} to: {df.columns.tolist()}")

    return df


def normalize_for_database(df):
    """
    Normalize pandas datatypes into Postgres compatible datatypes.
    """

    df = df.replace({pd.NA: None})

    df = df.astype(object)

    df = df.where(pd.notnull(df), None)

    return df

def apply_time_filter(df, source):
    """
    Filter for a specific time range.
    """

    time_filter = source.get("time_filter")
    if not time_filter:
        return df
    
    column = time_filter.get("column")
    start = time_filter.get("start")
    end = time_filter.get("end")

    if column not in df.columns:
        raise ValueError(f"Time filter column '{column}' not in dataframe")

    logger.info(f"Applying time filter on {column}: {start} -> {end}")

    df[column] = pd.to_datetime(df[column], errors="coerce")

    if start:
        df = df[df[column] >= pd.to_datetime(start)]

    if end:
        df = df[df[column] <= pd.to_datetime(end)]

    return df