from dotenv import load_dotenv

from config.config_loader import load_config
from database.database import database_setup, create_schema

from readers.readers import read_input
from cleaners.cleaners import normalize_columns, normalize_for_database

from validators.validators import (
    apply_schema_casts, 
    apply_rules, 
    enforce_required, 
    drop_duplicates
)

from loaders.loaders import load_upsert, write_rejects

from loggers.logging_config import (
    configure_logging,
    log_source_start,
    log_source_complete
)

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
