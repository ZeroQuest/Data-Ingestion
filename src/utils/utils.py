import pandas as pd
import os
from pathlib import Path

if os.getenv("RUNNING_IN_DOCKER") == "true":
    BASE_DIR = Path("/app")
else:
    BASE_DIR = Path(__file__).resolve().parents[2]

def project_path(*parts):
    return BASE_DIR.joinpath(*parts)

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
