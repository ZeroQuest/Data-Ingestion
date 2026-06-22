import pandas as pd
import pytest

from validators.validators import (
    apply_schema_casts,
    apply_rules,
    apply_rule,
    enforce_required,
    resolve_operand,
    parse_rule,
    build_mask,
    drop_duplicates,
)


def test_apply_schema_casts_float():
    df = pd.DataFrame({"prcp": ["1.5", "2.0"]})

    schema = {"prcp": "float"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert result["prcp"].dtype == "float64"
    assert len(rejects) == 0


def test_apply_schema_casts_datetime():
    df = pd.DataFrame({"date": ["2024-01-01"]})

    schema = {"date": "datetime"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert len(rejects) == 0


def test_apply_schema_casts_missing_column():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"date": "datetime"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert "date" in result.columns
    assert result["date"].isna().all()
    assert len(rejects) == 0


def test_apply_schema_casts_invalid_type():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"station": "orange"}

    with pytest.raises(ValueError):
        apply_schema_casts(df, schema, "test_source")


def test_apply_schema_casts_missing_float_column():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"awnd": "float"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert "awnd" in result.columns
    assert result["awnd"].isna().all()
    assert len(rejects) == 0


def test_apply_schema_casts_missing_string_column():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"name": "str"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert "name" in result.columns
    assert result["name"].isna().all()
    assert len(rejects) == 0


def test_apply_schema_casts_missing_int_column():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"elevation": "int"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert "elevation" in result.columns
    assert result["elevation"].isna().all()
    assert len(rejects) == 0


def test_apply_schema_casts_missing_datetime_column():
    df = pd.DataFrame({"station": ["ABC"]})

    schema = {"date": "datetime"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert "date" in result.columns
    assert result["date"].isna().all()
    assert len(rejects) == 0


def test_apply_schema_casts_invalid_float_creates_reject():
    df = pd.DataFrame({"prcp": ["1.5", "abc"]})

    schema = {"prcp": "float"}

    result, rejects = apply_schema_casts(df, schema, "test_source")

    assert pd.isna(result.loc[1, "prcp"])
    assert len(rejects) == 1
    assert rejects[0]["reason"] == "schema_cast_failed:prcp"


def test_enforce_required_valid():
    df = pd.DataFrame({"station": ["ABC"]})

    valid, rejects = enforce_required(df, ["station"], "test_source")

    assert len(valid) == 1
    assert len(rejects) == 0


def test_enforce_required_missing_pk():
    df = pd.DataFrame({"station": [None]})

    valid, rejects = enforce_required(df, ["station"], "test_source")

    assert len(valid) == 0
    assert len(rejects) == 1


def test_parse_rule():
    result = parse_rule("prcp >= 0")

    assert result == {
        "left": "prcp",
        "operator": ">=",
        "right": "0",
    }


def test_resolve_operand_numberic():
    df = pd.DataFrame()

    result = resolve_operand(df, "5")

    assert result == 5.0


def test_resolve_operand_column():
    df = pd.DataFrame({"tmax": [1, 2, 3]})

    result = resolve_operand(df, "tmax")

    assert result.equals(df["tmax"])


def test_build_mask_greater_equal():
    df = pd.DataFrame({"prcp": [1, -1, 2]})

    parsed = {
        "left": "prcp",
        "operator": ">=",
        "right": "0",
    }

    mask = build_mask(df, parsed)

    assert mask.tolist() == [True, False, True]


def test_build_mask_less_equal():
    df = pd.DataFrame(
        {
            "prcp": [1, 2, 3],
        }
    )

    parsed = {
        "left": "prcp",
        "operator": "<=",
        "right": "2",
    }

    mask = build_mask(df, parsed)

    assert mask.tolist() == [True, True, False]


def test_build_mask_invalid_operator():
    df = pd.DataFrame({"prcp": [1]})

    parsed = {
        "left": "prcp",
        "operator": ">",
        "right": "0",
    }

    with pytest.raises(ValueError):
        build_mask(df, parsed)


def test_apply_rule():
    df = pd.DataFrame({"prcp": [1, -1]})

    valid, rejects = apply_rule(df, "prcp >= 0")

    assert len(valid) == 1
    assert len(rejects) == 1


def test_apply_rules():
    df = pd.DataFrame({"prcp": [1, -1]})

    valid, rejects = apply_rules(df, ["prcp >= 0"], "test_source")

    assert len(valid) == 1
    assert len(rejects) == 1


def test_drop_duplicates():
    df = pd.DataFrame({"station": ["A", "A"]})

    valid, rejects = drop_duplicates(df, ["station"], "test_source")

    assert len(valid) == 1
    assert len(rejects) == 1


def test_drop_duplicates_no_duplicates():
    df = pd.DataFrame({"station": ["A", "B"]})

    valid, rejects = drop_duplicates(df, ["station"], "test_source")

    assert len(valid) == 2
    assert len(rejects) == 0
