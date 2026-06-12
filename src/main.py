import os
import psycopg
from dotenv import load_dotenv
import yaml
import json
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("../etl.log"),
            logging.StreamHandler()
        ]
    )

def log_source_start(source_name):
    logger.info("Starting source '%s'", source_name)

def log_source_complete(source_name, rows_loaded, rejects):
    logger.info(
        "Completed source '%s' (rows_loaded=%s rejects=%s)", 
        source_name,
        rows_loaded,
        rejects
    )

def load_config(path: str):
    """
    Loads the yaml configuration file from the path provided
    Returns the loaded yaml file
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            config_yml = yaml.safe_load(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Config file not found at path: {path}") from e
    except PermissionError as e:
        raise PermissionError(f"No permission to read config file: {path}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in config file: {path}") from e
    
    if config_yml is None:
        raise ValueError(f"Config file is empty or invalid: {path}")

    required_keys = ["defaults", "sources"]
    missing_keys = [key for key in required_keys if key not in config_yml]

    if missing_keys:
        raise ValueError(f"Config missing required keys: {missing_keys}")

    logger.info(f"Yaml config loaded at path: {path}")

    return config_yml


def database_setup(defaults):
    """
    Starts the database connection based on the url provided
        in defaults section in the config
    Returns the connection
    """

    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise ValueError(f"DATABASE_URL env value not set or invalid: {db_url}")

    try:
        conn = psycopg.connect(db_url)
    except Exception as e:
        raise ConnectionError(f"Failed to connect to database.") from e

    with conn.cursor() as cur:

        try:
            cur.execute("""
                SELECT version()
            """)
        except Exception as e:
            raise RuntimeError("Database connection validation failed during select version()") from e

        logger.info(f"Database connection established with version: {cur.fetchone()}")

    init_sql(conn)

    return conn


def init_sql(conn, path="../sql/init.sql"):
    """
    Reads and initializes the sql database from the init.sql file
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            sql = file.read()
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Missing sql initialization file at: {path}") from e

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    except Exception as e:
        raise RuntimeError(f"init.sql execution failed at {path}") from e

    logger.info(f"Database initialized from file at: {path}")

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

    try:
        schema = source["schema"]
        table = source["target_table"]
    except KeyError as e:
        raise ValueError(f"Source missing required keys: schema / target_table") from e
    
    if not schema:
        raise ValueError("Schema cannot be empty")

    pk = source.get("pk", [])

    with conn.cursor() as cur:

        # Build columns
        columns = []

        try:
            for col_name, col_type in schema.items():
                pg_type = TYPE_MAP[col_type]
                columns.append(f"{col_name} {pg_type}")
        except KeyError as e:
            raise ValueError(f"Unsupported schema type: {col_type} for column {col_name}") from e

        # Primary key
        if pk and not isinstance(pk, list):
            raise ValueError("Primary key must be a list")

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
    try:
        if source["type"] == "csv":
            return read_csv(source)
        elif source["type"] == "json":
            return read_json(source)
    except ValueError as e:
        raise ValueError(f"Unsupported source type {source['type']}") from e


def read_csv(source):
    """
    Reads a .csv file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])
    try:
        logger.info(f"CSV file read from: {path}")
        return pd.read_csv(path)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"CSV file not found at path: {path}") from e
    except ValueError as e:
        raise ValueError("Failed to parse CSV") from e


def read_json(source):
    """
    Reads a .json file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])

    # Load the entire json file
    try:
        with open(path, "r") as file:
            data = json.load(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found at path: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in file: {path}") from e
    

    # Get the root of a desired nested json based off the config
    root = source.get("json_root")

    if root:
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected top-level JSON object in {path}, "
                f"found {type(data).__name__}"
            )
        
        if root not in data:
            raise KeyError(f"json_root '{root}' not found in JSON file: {path}")

        # Gather the json metadata
        metadata = {key: value for key, value in data.items() if key != root}

        # Gather the nested data
        data = data[root]
    else:
        #Otherwise, metadata is empty
        metadata = {}

    #Validate extracted root data
    if not isinstance(data, (list, dict)):
        raise ValueError(
            f"JSON data must be a list or object, got "
            f"{type(data).__name__}"
        )

    # Create a dataframe based on the nested data
    try:
        df = pd.DataFrame(data)
    except Exception as e:
        raise ValueError(f"Failed to create DataFrame from JSON data in {path}") from e

    # Add the metadata to the dataframe
    for key, value in metadata.items():
        df[key] = value

    logger.info(f"JSON file read from: {path}")
    return df


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

        #Config validation
        if col not in df.columns:
            #Possibly change to a warning log later
            raise KeyError(f"Schema column missing in dataframe: {col}")
            
        try:
            target_type = PANDAS_TYPE_MAP[col_type]
        except KeyError as e:
            raise ValueError(f"Unsupported schema type '{col_type}' for column '{col}'") from e


        #Type conversion
        if col_type == "datetime":
            try:
                converted = pd.to_datetime(df[col], errors="coerce")
            except Exception as e:
                raise ValueError(f"Failed to convert column '{col}' to datetime") from e
        else:
            try:
                converted = df[col].astype(target_type)
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
        raise ValueError(f"Invalid rule syntax: {rule}")


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
        raise KeyError(f"Rule references missing column: {parsed['left']}")
    
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

    #Config validation
    if df is None:
        raise ValueError("Cannot load a None dataframe")
    
    if df.empty:
        return
    
    if not primary_key:
        raise ValueError(f"Primary key required for UPSERT into table '{table}'")
    
    if batch_size <= 0:
        raise ValueError(f"Batch size must be greater than zero, got {batch_size}")

    cols = list(df.columns)

    if not cols:
        raise ValueError(f"No dataframe columns available for table '{table}'")
    
    missing_pk = [col for col in primary_key if col not in cols]

    if missing_pk:
        raise KeyError(f"Primary key columns missing from dataframe: {missing_pk}")

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

    try:
        with conn.cursor() as cur:
            for row in rows:
                batch.append(row)

                if len(batch) >= batch_size:
                    cur.executemany(sql, batch)
                    batch.clear()

            if batch:
                cur.executemany(sql, batch)
    except Exception as e:
        raise RuntimeError(f"Failed loading data into table '{table}'") from e

    try:
        conn.commit()
        logger.info(f"Loaded {len(df)} rows to {table}")
    except Exception as e:
        raise RuntimeError(f"Failed committing transaction for table '{table}'")


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
    try:
        with conn.cursor() as cur:

            for i in range(0, len(rejects), batch_size):
                batch = rejects[i : i + batch_size]
                
                try:
                    params = [
                        (
                            reject["source_name"],
                            json.dumps(reject["raw_payload"]),
                            reject["reason"],
                        )
                        for reject in batch
                    ]
                except KeyError as e:
                    raise ValueError(f"Malformed reject record missing required key: {e}") from e
                except TypeError as e:
                    raise RuntimeError("Failed writing rejects to stg_regets") from e

                cur.executemany(sql, params)
    except Exception as e:
        raise RuntimeError("Failed writing rejects to stg_rejects") from e

    try:    
        conn.commit()
        logger.info(f"Wrote {len(rejects)} to stg_rejects.")
    except Exception as e:
        raise RuntimeError("Failed committing reject records") from e


def run_source(connection, source, defaults):
    """
    Runs the ETL pipeline for a given source.
    """
    log_source_start(str(source["name"]))
    df = read_input(source)
    df = normalize_columns(df)
    df, rejects = apply_schema_casts(df, source["schema"], source["name"])
    df = df[list(source["schema"].keys())]
    df, enforce_required_rejects = enforce_required(df, source["pk"], source["name"])
    rejects += enforce_required_rejects
    df, rules_rejects = apply_rules(df, source["rules"], source["name"])
    rejects += rules_rejects
    df, duplicate_rejects = drop_duplicates(df, source["pk"], source["name"])
    rejects += duplicate_rejects
    df = normalize_for_database(df)
    load_upsert(
        connection,
        df,
        table=source["target_table"],
        primary_key=source["pk"],
        batch_size=defaults["batch_size"],
    )
    write_rejects(connection, rejects, defaults["batch_size"])
    log_source_complete(str(source), len(df), len(rejects))


def main():
    load_dotenv()

    path: str = "../config/sources.yml"
    config = load_config(path)

    defaults = config["defaults"]
    sources = config["sources"]

    configure_logging()

    connection = database_setup(defaults)

    for source in sources:
        create_schema(connection, source)

    for source in sources:
        run_source(connection, source, defaults)

    connection.close()


if __name__ == "__main__":
    main()
