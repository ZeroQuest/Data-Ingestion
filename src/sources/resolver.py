from loggers.logging_config import logger

def resolve_source(source):
    """
    Turn high-level dataset definitions into executable ingestion configs.
    """

    source_type = source.get("type")

    if source_type == "noaa_gsom":
        return resolve_noaa_gsom(source)
    elif source_type == "open_meteo":
        return resolve_open_meteo(source)
    # We passthrough for generic sources
    return source

def resolve_noaa_gsom(source):
    """
    Expands NOAA GSOM config into http_csv ingestion config
    """
    base_url = source.get("base_url")
    stations = source.get("stations", [])

    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("noaa_gsom requires 'base_url'")
    if not stations or not isinstance(stations, list):
        raise ValueError("noaa_gsom requires 'stations'")
    
    logger.info(f"Resolving NOAA GSOM source for {len(stations)} stations")

    urls = []

    for station in stations:
        if not isinstance(station, str) or not station.strip():
            logger.warning(f"Skipping invalid station id: {station}")
            continue

        urls.append(f"{base_url.rstrip('/')}/{station}.csv")
    
    if not urls:
        raise ValueError("noaa_gsom produced no valid URLs")

    # Return normalized config for existing pipeline
    resolved = {
        "type": "http_csv",
        "urls": urls,

        "name": source.get("name"),
        "target_table": source.get("target_table"),
        "pk": source.get("pk"),
        "schema": source.get("schema"),
        "rules": source.get("rules"),

        "time_filter": source.get("time_filter")
    }

    return resolved

def resolve_open_meteo(source):
    """
    Expands Open Meteo config into http_json config
    """
    base_url = source["base_url"]

    if not base_url:
        raise ValueError("open_meteo requires 'base_url'")

    params = {
        "latitude": source["latitude"],
        "longitude": source["longitude"],
        "start_date": source["start_date"],
        "end_date": source["end_date"],
        "timezone": "UTC",
    }

    hourly = source["params"]["hourly"]
    params["hourly"] = ",".join(hourly)

    url = base_url + "?" + "&".join(
        f"{key}={value}" for key, value in params.items()
    )

    logger.info(
        f"Resolving source: {source.get('name')} -> http_json | "
        f"lat={source.get('latitude')} lon={source.get('longitude')} "
        f"range={source.get('start_date')}:{source.get('end_date')}"
    )

    return {
        "type": "http_json",
        "url": url,

        "name": source["name"],
        "target_table": source["target_table"],
        "pk": source["pk"],
        "schema": source["schema"],
        "rules": source["rules"],

        "json_root": "hourly",
    }