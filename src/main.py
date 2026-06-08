import os
import psycopg
from dotenv import load_dotenv
import yaml
import json
import pandas as pd


def load_config(path: str):
    """
    Loads the yaml configuration file from the path provided
    Returns the loaded yaml file
    """
    with open(path, "r", encoding="utf-8") as file:
        config_yml = yaml.safe_load(file)

    return config_yml


def database_setup(defaults):
    """
    Starts the database connection based on the url provided
        in defaults section in the config
    Returns the connection
    """

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
    """
    Reads and initializes the sql database from the init.sql file
    """

    with open(path, "r", encoding="utf-8") as file:
        sql = file.read()

    with conn.cursor() as cur:
        cur.execute(sql)

    conn.commit()


def create_schema(conn, source):
    """
    Wraps the create table functionality to provide a
        named schema function for pipeline readability
    """
    create_table(conn, source)


def create_table(conn, source):
    """
    Creates a table in the database based on the schema in the
        yaml config
    """

    # Map for mapping python data types to SQL data types
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
    """
    Reads the source input based on the configuration
    Returns a pandas dataframe
    """
    if source["type"] == "csv":
        return read_csv(source)
    elif source["type"] == "json":
        return read_json(source)


def read_csv(source):
    """
    Reads a .csv file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])
    return pd.read_csv(path)


def read_json(source):
    """
    Reads a .json file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])

    # Load the entire json file
    with open(path, "r") as file:
        data = json.load(file)

    # Get the root of a desired nested json based off the config
    root = source.get("json_root")

    # Gather the json metadata
    metadata = {key: value for key, value in data.items() if key != root}

    # Gather the nested data
    if root:
        data = data[root]

    # Create a dataframe based on the nested data
    df = pd.DataFrame(data)

    # Add the metadata to the dataframe
    for key, value in metadata.items():
        df[key] = value

    return df


def normalize_columns(df):
    """
    Normalizes the data for entry into sql
    """
    df.columns = df.columns.str.strip()
    df.columns = df.columns.str.lower()
    df.columns = df.columns.str.replace(" ", "_")

    return df


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

        if col not in df.columns:
            continue
            # Raise error later?

        target_type = PANDAS_TYPE_MAP[col_type]

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
    parsed = parse_rule(rule)

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
    left = df[parsed["left"]]
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

    mask = df.duplicated(subset=primary_key, keep="first")

    bad_rows = df[mask]
    records = bad_rows.to_dict("records")

    # For every duplicate, call emit_reject() with the reason "duplicate_primary_key"
    rejects = [
        emit_reject(source_name, reason="duplicate_primary_key", row=record)
        for record in records
    ]

    valid = df[~mask].copy()
    valid = valid.reset_index(drop=True)

    return valid, rejects


def normalize_for_database(df):
    """
    Normalize pandas datatypes into Postgres compatible datatypes.
    """

    df = df.replace({pd.NA: None})

    df = df.astype(object)

    df = df.where(pd.notnull(df), None)

    return df


def load_upsert(conn, df, table, primary_key, batch_size):
    """
    Loads final data into the database via the UPSERT paradigm.
    """
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


# Unused Remove before final
def normalize_for_json(obj):
    """ """
    if isinstance(obj, dict):
        return {key: normalize_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [normalize_for_json(value) for value in obj]

    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if hasattr(obj, "item"):
        return obj.item()

    return obj


# Unused


def write_rejects(conn, rejects, batch_size):
    """
    Writes all rejected rows into the stg_rejects table in the database.
    """
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
    """
    Runs the ETL pipeline for a given source.
    """

    df = read_input(source)
    # print(df)
    df = normalize_columns(df)
    # print(df)
    df, rejects = apply_schema_casts(df, source["schema"], source["name"])
    df = df[list(source["schema"].keys())]
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
