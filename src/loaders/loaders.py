import logging
import json

logger = logging.getLogger(__name__)


def load_upsert(conn, df, table, primary_key, batch_size):
    """
    Loads final data into the database via the UPSERT paradigm.
    """

    # Config validation
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
        raise RuntimeError(f"Failed committing transaction for table '{table}'") from e


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
                    raise ValueError(
                        f"Malformed reject record missing required key: {e}"
                    ) from e
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