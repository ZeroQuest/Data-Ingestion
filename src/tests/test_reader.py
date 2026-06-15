import json
import pandas as pd
import pytest

from readers.readers import (
    read_input, 
    read_csv, 
    read_json
)

def test_read_input_routes_to_csv(tmp_path, monkeypatch):
    df = pd.DataFrame({"a": [1]})

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

    payload = {
        "meta": 123,
        "data": [{"a": 1}, {"a": 2}]
    }

    file.write_text(json.dumps(payload))

    source = {
        "path": str(file),
        "json_root": "data"
    }

    monkeypatch.chdir(tmp_path.parent)

    df = read_json(source)

    assert len(df) == 2
    assert df["meta"].iloc[0] == 123

def test_read_json_missing_root(tmp_path, monkeypatch):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"other": []}))

    source = {
        "path": str(file),
        "json_root": "data"
    }

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