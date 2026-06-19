import pandas as pd
import logging
from utils.utils import emit_reject

logger = logging.getLogger(__name__)


def apply_schema_casts(df, schema, source_name):
    """
    Applies the schema type casting from yaml to pandas data types
    Returns the rejects dataframe and the casted dataframe
    """

    # Maps yaml data types to pandas data types
    PANDAS_TYPE_MAP = {
        "int": "Int64",
        "float": "float64",
        "str": "string",
        "datetime": "datetime64[ns]",
    }

    rejects = []

    for col, col_type in schema.items():

        # Config validation
        if col not in df.columns:
            # Possibly change to a warning log later
            logger.warning(f"[{source_name}] Missing column '{col}' filling with NA")
            df[col] = pd.Series([pd.NA] * len(df))

        try:
            target_type = PANDAS_TYPE_MAP[col_type]
        except KeyError as e:
            raise ValueError(
                f"Unsupported schema type '{col_type}' for column '{col}'"
            ) from e

        # Type conversion
        if col_type == "datetime":
            try:
                converted = pd.to_datetime(df[col], errors="coerce")
            except Exception as e:
                raise ValueError(f"Failed to convert column '{col}' to datetime") from e
        elif col_type == "str":
            try:
                converted = df[col].astype(col_type)
            except Exception as e:
                raise ValueError(f"Failed to cast column {col} to {target_type}")
        else:
            try:
                converted = pd.to_numeric(df[col], errors="coerce")
            except Exception as e:
                raise ValueError(f"Failed to cast column {col} to {target_type}") from e

        bad_rows = df[converted.isna() & df[col].notna()]

        records = bad_rows.to_dict("records")

        rejects.extend(
            [
                emit_reject(source_name, reason=f"schema_cast_failed:{col}", row=record)
                for record in records
            ]
        )

        df[col] = converted

    return df, rejects


def enforce_required(df, primary_key, source_name):
    """
    Checks rows to ensure they have primary key data,
        otherwise reject those rows to a rejects dataframe
    Returns the reject dataframe and the valid dataframe
    """
    rejects = []

    reject_mask = df[primary_key].isna().any(axis=1)

    bad_rows = df[reject_mask]

    records = bad_rows.to_dict("records")

    rejects.extend(
        [
            emit_reject(source_name, reason="missing_primary_key", row=record)
            for record in records
        ]
    )

    valid_df = df[~reject_mask].copy()

    return valid_df, rejects


def apply_rules(df, rules, source_name):
    """
    Applies the rules defined in the yaml config
    Returns a rejects dataframe and the valid dataframe
    """
    rejects = []

    if not rules:
        raise ValueError("Rules list is empty")

    for rule in rules:
        df, bad_rows = apply_rule(df, rule)

        records = bad_rows.to_dict("records")

        rejects.extend(
            [
                emit_reject(source_name, reason=f"rule_violation:{rule}", row=record)
                for record in records
            ]
        )

    return df, rejects


def apply_rule(df, rule):
    """
    Applies a singular rule from the config
    Returns a valid dataframe and a rejects dataframe
    """
    try:
        parsed = parse_rule(rule)
    except ValueError as e:
        raise ValueError(f"Invalid rule syntax: {rule}") from e

    mask = build_mask(df, parsed)

    rejects = df[~mask].copy()
    valid = df[mask].copy()

    return valid, rejects


def parse_rule(rule: str):
    """
    Parses a rule from the config
    Returns the left element, the operator, and the right element

    Note: Serves as a small baseline for AST style solutions
    """
    left, operator, right = rule.split()

    return {"left": left, "operator": operator, "right": right}


def resolve_operand(df, operand: str):
    """
    Resolve the right hand operand of a comparison expression.

    If the operand can be parsed as a number, return it as a float.
    Otherwise, return it as a dataframe column name and return the corresponding pandas series.
    """
    try:
        return float(operand)
    except ValueError:
        return df[operand]


def build_mask(df, parsed):
    """
    Builds a mask that filters valid operations.

    Returns the evaluation of a valid operation or raises a ValueError for an
        unsupported operation.
    """

    try:
        left = df[parsed["left"]]
    except KeyError as e:
        raise KeyError(f"Rule references missing column: {parsed['left']}") from e

    right = resolve_operand(df, parsed["right"])
    operator = parsed["operator"]

    if operator == ">=":
        return left >= right
    elif operator == "<=":
        return left <= right
    else:
        raise ValueError(f"Unsupported operator: {operator}")


def drop_duplicates(df, primary_key, source_name):
    """
    Drops rows with duplicate primary key values.

    Note: Current implementation keeps the first instance.
    """
    num_before = len(df)

    mask = df.duplicated(subset=primary_key, keep="first")
    num_after = len(mask)
    removed_rows = num_before - num_after

    bad_rows = df[mask]
    records = bad_rows.to_dict("records")

    # For every duplicate, call emit_reject() with the reason "duplicate_primary_key"
    rejects = [
        emit_reject(source_name, reason="duplicate_primary_key", row=record)
        for record in records
    ]

    if removed_rows > 0:
        logger.info(f"Removed {removed_rows} duplicate rows.")

    valid = df[~mask].copy()
    valid = valid.reset_index(drop=True)

    return valid, rejects
