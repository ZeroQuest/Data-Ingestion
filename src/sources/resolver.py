from loggers.logging_config import logger

def resolve_source(source):
    """
    Turn high-level dataset definitions into executable ingestion configs.
    """

    source_type = source.get("type")

    if source_type == "noaa_gsom":
        return resolve_noaa_gsom(source)
    
    # We passthrough for generic sources
    return source

def resolve_noaa_gsom(source):
    """
    Expands NOAA GSOM config into http_csv ingestion config
    """
    base_url = source.get("base_url")
    stations = source.get("stations", [])

    if not base_url:
        raise ValueError("noaa_gsom requires 'base_url'")
    if not stations:
        raise ValueError("noaa_gsom requires 'stations'")
    
    logger.info(f"Resolving NOAA GSOM source for {len(stations)} stations")

    urls = [
        f"{base_url.rstrip('/')}/{station}.csv"
        for station in stations
    ]

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