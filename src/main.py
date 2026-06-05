import os
import psycopg
from dotenv import load_dotenv
import yaml
import json
import pandas as pd


def load_config(path: str):

    with open(path, "r", encoding="utf-8") as file:
        config_yml = yaml.safe_load(file)

    return config_yml


def database_setup(defaults):

    db_url = os.getenv("DATABASE_URL")

    conn = psycopg.connect(db_url)

    with conn.cursor() as cur:

        cur.execute("""
            SELECT version()
        """)
        print(cur.fetchone())

    init_sql(conn)

    return conn


def init_sql(conn, path="../sql/init.sql"):

    with open(path, "r", encoding="utf-8") as file:
        sql = file.read()

    with conn.cursor() as cur:
        cur.execute(sql)

    conn.commit()


def create_schema(conn, source):
    create_table(conn, source)


def create_table(conn, source):

    TYPE_MAP = {
        "int": "INTEGER",
        "float": "DOUBLE PRECISION",
        "str": "TEXT",
        "datetime": "TIMESTAMP",
    }

    schema = source["schema"]
    table = source["target_table"]
    pk = source.get("pk", [])

    with conn.cursor() as cur:

        # Build columns
        columns = []
        for col_name, col_type in schema.items():
            pg_type = TYPE_MAP[col_type]
            columns.append(f"{col_name} {pg_type}")

        # Primary key
        pk_clause = ""
        if pk:
            pk_clause = f", PRIMARY KEY ({', '.join(pk)})"

        # SQL
        columns_sql = ",\n  ".join(columns)

        sql = f"""
            CREATE TABLE IF NOT EXISTS {table} (
                {columns_sql}
                {pk_clause}
            );
        """

        print(f"[DDL] Creating table: {table}")
        cur.execute(sql)
    conn.commit()


def read_input(source):
    # print(source)

    if source["type"] == "csv":
        path = os.path.join("..", source["path"])
        return pd.read_csv(path)


def normalize_columns(df):
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.lower()
    df.columns = df.columns.str.replace(" ", "_")

    return df


def apply_schema_casts(df, schema, source_name):

    PY_TYPE_MAP = {
        "int": "Int64",
        "float": "float64",
        "str": "string",
        "datetime": "datetime64[ns]",
    }

    rejects = []

    for col, col_type in schema.items():

        if col not in df.columns:
            continue
            # Raise error later?

        target_type = PY_TYPE_MAP[col_type]

        if col_type == "datetime":
            converted = pd.to_datetime(df[col], errors="coerce")
        else:
            converted = df[col].astype(target_type)

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
    rejects = []

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
    parsed = parse_rule(rule)

    mask = build_mask(df, parsed)

    rejects = df[~mask].copy()
    valid = df[mask].copy()

    return valid, rejects


def parse_rule(rule: str):
    left, operand, right = rule.split()

    return {"left": left, "operand": operand, "right": right}


def resolve_operand(df, operand: str):
    try:
        return float(operand)
    except ValueError:
        return df[operand]


def build_mask(df, parsed):
    left = df[parsed["left"]]
    right = resolve_operand(df, parsed["right"])
    operand = parsed["operand"]

    if operand == ">=":
        return left >= right
    else:
        raise ValueError(f"Unsupported operator: {operand}")


def drop_duplicates(df, primary_key, source_name):

    mask = df.duplicated(subset=primary_key, keep="first")

    bad_rows = df[mask]
    records = bad_rows.to_dict("records")

    rejects = [
        emit_reject(source_name, reason="duplicate_primary_key", row=record)
        for record in records
    ]

    valid = df[~mask].copy()
    valid = valid.reset_index(drop=True)

    return valid, rejects


def normalize_for_database(df):

    df = df.replace({pd.NA: None})

    df = df.astype(object)

    df = df.where(pd.notnull(df), None)

    return df


def load_upsert(conn, df, table, primary_key, batch_size):
    cols = list(df.columns)

    col_sql = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))

    conflict_cols = ", ".join(primary_key)

    update_cols = ", ".join(
        f"{col} = EXCLUDED.{col}" for col in cols if col not in primary_key
    )

    sql = f"""
        INSERT INTO {table} ({col_sql})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_cols})
        DO UPDATE SET {update_cols}
    """

    rows = df.itertuples(index=False, name=None)

    batch = []

    with conn.cursor() as cur:
        for row in rows:
            batch.append(row)

            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                batch.clear()

        if batch:
            cur.executemany(sql, batch)

    conn.commit()


def emit_reject(source_name, reason, row):
    payload = {}

    for key, value in row.items():
        if isinstance(value, pd.Timestamp):
            value = value.isoformat()
        elif pd.isna(value):
            value = None

        payload[key] = value
    return {"source_name": source_name, "reason": reason, "raw_payload": payload}


def normalize_for_json(obj):
    if isinstance(obj, dict):
        return {key: normalize_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [normalize_for_json(value) for value in obj]

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if hasattr(obj, "item"):
        return obj.item()

    return obj


def write_rejects(conn, rejects, batch_size):

    if not rejects:
        return

    sql = """
        INSERT INTO stg_rejects (source_name, raw_payload, reason)
        VALUES (%s, %s, %s)
    """

    with conn.cursor() as cur:

        for i in range(0, len(rejects), batch_size):
            batch = rejects[i : i + batch_size]
            params = [
                (
                    reject["source_name"],
                    json.dumps(reject["raw_payload"]),
                    reject["reason"],
                )
                for reject in batch
            ]

            cur.executemany(sql, params)
    conn.commit()


def run_source(connection, source, defaults):
    df = read_input(source)
    # print(df)
    df = normalize_columns(df)
    # print(df)
    df, rejects = apply_schema_casts(df, source["schema"], source["name"])
    # print(df)
    df, enforce_required_rejects = enforce_required(df, source["pk"], source["name"])
    # print(df)
    rejects += enforce_required_rejects
    df, rules_rejects = apply_rules(df, source["rules"], source["name"])
    # print(df)
    rejects += rules_rejects
    df, duplicate_rejects = drop_duplicates(df, source["pk"], source["name"])
    rejects += duplicate_rejects
    # print(df[df.duplicated(subset=source["pk"], keep=False)])
    # print(df)
    df = normalize_for_database(df)
    load_upsert(
        connection,
        df,
        table=source["target_table"],
        primary_key=source["pk"],
        batch_size=defaults["batch_size"],
    )
    write_rejects(connection, rejects, defaults["batch_size"])


def main():
    load_dotenv()

    path: str = "../config/sources.yml"
    config = load_config(path)

    defaults = config["defaults"]
    sources = config["sources"]

    # print(config["sources"])

    connection = database_setup(defaults)

    for source in sources:
        create_schema(connection, source)

    for source in sources:
        run_source(connection, source, defaults)

    connection.close()


if __name__ == "__main__":
    main()
