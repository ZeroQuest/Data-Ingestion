import logging

logger = logging.getLogger(__name__)

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.FileHandler("../etl.log"), logging.StreamHandler()],
    )


def log_source_start(source_name):
    logger.info("Starting source '%s'", source_name)


def log_source_complete(source_name, rows_loaded, rejects):
    logger.info(
        "Completed source '%s' (rows_loaded=%s rejects=%s)",
        source_name,
        rows_loaded,
        rejects,
    )