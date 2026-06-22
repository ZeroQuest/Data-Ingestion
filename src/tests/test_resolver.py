import pytest
from sources.resolver import (
    resolve_noaa_gsom,
    resolve_open_meteo,
    resolve_source
)

def test_noaa_resolver_expands_urls():
    source = {
        "name": "noaa_test",
        "type": "noaa_gsom",
        "base_url": "https://example.com/data",
        "stations": ["US1", "US2"],
        "target_table": "stg",
        "pk": ["station"],
        "schema": {"station": "str"},
        "rules": []
    }

    resolved = resolve_noaa_gsom(source)

    assert resolved["type"] == "http_csv"
    assert len(resolved["urls"]) == 2
    assert resolved["urls"][0].endswith("US1.csv")

def test_noaa_missing_stations_raises():
    source = {
        "name": "bad",
        "type": "noaa_gsom",
        "base_url": "x",
        "stations": []
    }

    with pytest.raises(ValueError):
        resolve_noaa_gsom(source)

def test_open_meteo_url_build():
    source = {
        "name": "open_meteo",
        "type": "open_meteo",
        "base_url": "https://archive-api.open-meteo.com/v1/archive",
        "latitude": 10,
        "longitude": 20,
        "start_date": "2024-01-01",
        "end_date": "2024-01-02",
        "params": {
            "hourly": ["temperature_2m"]
        },
        "target_table": "t",
        "pk": ["time"],
        "schema": {},
        "rules": []
    }

    resolved = resolve_open_meteo(source)

    assert "temperature_2m" in resolved["url"]
    assert "latitude=10" in resolved["url"]