import os
import psycopg
import logging
from pathlib import Path
from utils.utils import project_path

logger = logging.getLogger(__name__)


def database_setup(defaults):
    """
    Starts the database connection based on the url provided
        in defaults section in the config
    Returns the connection
    """

    db_url = os.getenv(defaults["db_url_env"])

    if not db_url:
        raise ValueError(f"DATABASE_URL env value not set or invalid: {db_url}")

    try:
        conn = psycopg.connect(db_url)
    except Exception as e:
        raise ConnectionError("Failed to connect to database.") from e

    with conn.cursor() as cur:

        try:
            cur.execute("""
                SELECT version()
            """)
        except Exception as e:
            raise RuntimeError(
                "Database connection validation failed during select version()"
            ) from e

        logger.info(f"Database connection established with version: {cur.fetchone()}")

    init_sql(conn)

    return conn


def init_sql(conn, path=None):
    """
    Reads and initializes the sql database from the init.sql file
    """
    if path is None:
        path = project_path("sql", "init.sql")
    else:
        path = Path(path)

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
        raise ValueError("Source missing required keys: schema / target_table") from e

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
            raise ValueError(
                f"Unsupported schema type: {col_type} for column {col_name}"
            ) from e

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
