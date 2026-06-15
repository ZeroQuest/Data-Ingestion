import pandas as pd
import pytest
from unittest.mock import MagicMock

from loaders.loaders import load_upsert, write_rejects


def test_load_insert():
    df = pd.DataFrame({"id": [1, 2], "value": ["a", "b"]})

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    load_upsert(conn, df, table="test_table", primary_key=["id"], batch_size=100)

    assert cur.executemany.called
    assert conn.commit.called


def test_load_upsert_none_df():
    conn = MagicMock()

    with pytest.raises(ValueError):
        load_upsert(conn, None, "t", ["id"], 10)


def test_load_upsert_empty_df():
    conn = MagicMock()
    df = pd.DataFrame()

    load_upsert(conn, df, "t", ["id"], 10)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()


def test_load_upsert_missing_pk():
    conn = MagicMock()
    df = pd.DataFrame({"value": [1]})

    with pytest.raises(KeyError):
        load_upsert(conn, df, "t", ["id"], 10)


def test_load_upsert_invalid_batch_size():
    conn = MagicMock()
    df = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError):
        load_upsert(conn, df, "t", ["id"], 0)


def test_load_upsert_batches_correctly():
    df = pd.DataFrame({"id": [1, 2, 3], "value": ["a", "b", "c"]})

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    load_upsert(conn, df, "t", ["id"], batch_size=2)

    assert cur.executemany.call_count == 2


def test_write_rejects_writes_batches():
    rejects = [
        {"source_name": "s1", "raw_payload": {"a": 1}, "reason": "bad"},
        {"source_name": "s1", "raw_payload": {"a": 2}, "reason": "bad"},
    ]

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    write_rejects(conn, rejects, batch_size=1)

    assert cur.executemany.call_count == 2
    conn.commit.assert_called()


def test_write_rejects_missing_keys():
    rejects = [{"bad": "data"}]

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur

    with pytest.raises(ValueError):
        write_rejects(conn, rejects, 10)
