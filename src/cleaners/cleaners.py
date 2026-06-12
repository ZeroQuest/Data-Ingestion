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
