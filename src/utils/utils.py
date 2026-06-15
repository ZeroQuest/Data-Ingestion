import pandas as pd


def emit_reject(source_name, reason, row):
    """
    Emits a rejected row based on the source and reason
    Returns the rejected row enriched with source and reason
    """
    payload = {}

    for key, value in row.items():
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        elif pd.isna(value):
            value = None

        payload[key] = value
    return {"source_name": source_name, "reason": reason, "raw_payload": payload}
