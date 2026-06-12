import logging
import yaml

logger = logging.getLogger(__name__)

def load_config(path: str):
    """
    Loads the yaml configuration file from the path provided
    Returns the loaded yaml file
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            config_yml = yaml.safe_load(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Config file not found at path: {path}") from e
    except PermissionError as e:
        raise PermissionError(f"No permission to read config file: {path}") from e
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in config file: {path}") from e

    if config_yml is None:
        raise ValueError(f"Config file is empty or invalid: {path}")

    required_keys = ["defaults", "sources"]
    missing_keys = [key for key in required_keys if key not in config_yml]

    if missing_keys:
        raise ValueError(f"Config missing required keys: {missing_keys}")

    logger.info(f"Yaml config loaded at path: {path}")

    return config_yml
