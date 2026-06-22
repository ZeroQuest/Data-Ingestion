import json
import pandas as pd
import pytest
import requests

from unittest.mock import Mock

from readers.readers import (
    read_input,
    read_csv,
    read_json,
    read_http_csv,
    read_http_json,
)


def test_read_input_routes_to_csv(tmp_path, monkeypatch):
    file = tmp_path / "data.csv"
    file.write_text("a\n1\n")

    source = {"type": "csv", "path": str(file)}

    monkeypatch.chdir(tmp_path.parent)

    result = read_input(source)

    assert isinstance(result, pd.DataFrame)
    assert "a" in result.columns


def test_read_input_routes_to_json(tmp_path, monkeypatch):
    file = tmp_path / "data.json"

    file.write_text(json.dumps([{"a": 1}]))

    source = {"type": "json", "path": str(file)}

    monkeypatch.chdir(tmp_path.parent)

    result = read_input(source)

    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["a"] == 1


def test_read_input_unsupported_type():
    source = {"type": "xml", "path": "x.xml"}

    with pytest.raises(ValueError):
        read_input(source)


def test_read_csv_reads_file(tmp_path, monkeypatch):
    file = tmp_path / "data.csv"
    file.write_text("a\n1\n2\n")

    source = {"path": str(file)}

    monkeypatch.chdir(tmp_path.parent)

    df = read_csv(source)

    assert df["a"].tolist() == [1, 2]
    assert len(df) == 2


def test_read_csv_file_not_found():
    source = {"path": "missing.csv"}

    with pytest.raises(FileNotFoundError):
        read_csv(source)


def test_read_json_flat(tmp_path, monkeypatch):
    file = tmp_path / "data.json"
    file.write_text(json.dumps([{"a": 1}, {"a": 2}]))

    source = {"path": str(file)}

    monkeypatch.chdir(tmp_path.parent)

    df = read_json(source)

    assert len(df) == 2
    assert df.iloc[0]["a"] == 1


def test_read_json_root_and_metadata(tmp_path, monkeypatch):
    file = tmp_path / "data.json"

    payload = {"meta": 123, "data": [{"a": 1}, {"a": 2}]}

    file.write_text(json.dumps(payload))

    source = {"path": str(file), "json_root": "data"}

    monkeypatch.chdir(tmp_path.parent)

    df = read_json(source)

    assert len(df) == 2
    assert df["meta"].iloc[0] == 123


def test_read_json_missing_root(tmp_path, monkeypatch):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"other": []}))

    source = {"path": str(file), "json_root": "data"}

    monkeypatch.chdir(tmp_path.parent)

    with pytest.raises(KeyError):
        read_json(source)


def test_read_json_invalid_json(tmp_path, monkeypatch):
    file = tmp_path / "data.json"
    file.write_text("{bad json}")

    source = {"path": str(file)}

    monkeypatch.chdir(tmp_path.parent)

    with pytest.raises(ValueError):
        read_json(source)


def test_read_http_csv(monkeypatch):
    response = Mock()
    response.text = "id,name\n1,bob\n2,alice"
    response.raise_for_status.return_value = None

    monkeypatch.setattr(
        "readers.readers.requests.get",
        lambda url, timeout: response,
    )

    df = read_http_csv({"url": "https://example.com/test.csv"})

    assert len(df) == 2
    assert list(df.columns) == ["id", "name"]


def test_read_http_csv_multiple_urls(monkeypatch):

    response = Mock()
    response.text = "id\n1"
    response.raise_for_status.return_value = None

    monkeypatch.setattr(
        "readers.readers.requests.get",
        lambda url, timeout: response,
    )

    df = read_http_csv(
        {"urls": ["https://example.com/a.csv", "https://example.com/b.csv"]}
    )

    assert len(df) == 2

    def test_read_http_csv_connection_error(monkeypatch):

        def fake_get(url, timeout):
            raise requests.RequestException("network failure")

        monkeypatch.setattr(
            "readers.readers.requests.get",
            fake_get,
        )

        with pytest.raises(ConnectionError):
            read_http_csv({"url": "https://example.com/test.csv"})


def test_read_http_csv_missing_url():

    with pytest.raises(ValueError):
        read_http_csv({})


def test_read_http_json(monkeypatch):

    response = Mock()

    response.raise_for_status.return_value = None
    response.json.return_value = {
        "latitude": 35.43,
        "longitude": -82.53,
        "hourly": {
            "time": [
                "2024-01-01T00:00",
                "2024-01-01T01:00",
            ],
            "temperature_2m": [
                12.5,
                13.1,
            ],
        },
    }

    monkeypatch.setattr(
        "readers.readers.requests.get",
        lambda url, timeout: response,
    )

    df = read_http_json(
        {
            "url": "https://api.open-meteo.com",
            "json_root": "hourly",
        }
    )

    assert len(df) == 2
    assert "latitude" in df.columns
    assert "longitude" in df.columns
    assert "temperature_2m" in df.columns


def test_read_http_json_connection_error(monkeypatch):

    def fake_get(url, timeout):
        raise requests.RequestException("connection failure")

    monkeypatch.setattr(
        "readers.readers.requests.get",
        fake_get,
    )

    with pytest.raises(ConnectionError):
        read_http_json({"url": "https://api.open-meteo.com"})


def test_read_http_json_invalid_json(monkeypatch):

    response = Mock()

    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("invalid json")

    monkeypatch.setattr(
        "readers.readers.requests.get",
        lambda url, timeout: response,
    )

    with pytest.raises(ValueError):
        read_http_json({"url": "https://api.open-meto.com"})


def test_read_http_json_invalid_root(monkeypatch):

    response = Mock()

    response.raise_for_status.return_value = None
    response.json.return_value = {
        "latitude": 35.43,
        "longitude": -82.53,
    }

    monkeypatch.setattr(
        "readers.readers.requests.get",
        lambda url, timeout: response,
    )

    with pytest.raises(ValueError):
        read_http_json(
            {
                "url": "https://api.open-meteo.com",
                "json_root": "hourly",
            }
        )
