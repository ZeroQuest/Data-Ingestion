import pandas as pd

from utils.utils import emit_reject


def test_emit_reject_basic_row():
    row = {"a": 1, "b": "x"}

    result = emit_reject("source1", "bad_row", row)

    assert result["source_name"] == "source1"
    assert result["reason"] == "bad_row"
    assert result["raw_payload"] == {"a": 1, "b": "x"}


def test_emit_reject_handles_timestamp():
    ts = pd.Timestamp("2026-01-01 12:00:00")

    row = {"time": ts}

    result = emit_reject("source1", "timestamp_test", row)

    assert result["raw_payload"]["time"] == ts.isoformat()


def test_emit_reject_handles_nan_as_none():
    row = {"value": float("nan")}

    result = emit_reject("source1", "nan_test", row)

    assert result["raw_payload"]["value"] is None


def test_emit_reject_handles_pdna_as_none():
    row = {"value": pd.NA}

    result = emit_reject("source1", "pdna_test", row)

    assert result["raw_payload"]["value"] is None


def test_emit_reject_mixed_row():
    ts = pd.Timestamp("2026-01-01 00:00:00")

    row = {"id": 1, "time": ts, "missing": pd.NA, "value": 10.5}

    result = emit_reject("sensor", "mixed", row)

    assert result["source_name"] == "sensor"
    assert result["reason"] == "mixed"

    assert result["raw_payload"] == {
        "id": 1,
        "time": ts.isoformat(),
        "missing": None,
        "value": 10.5,
    }


def test_emit_reject_no_mutation():
    ts = pd.Timestamp("2026-01-01")

    row = {"time": ts, "value": pd.NA}

    original = row.copy()

    emit_reject("src", "test", row)

    assert row == original
