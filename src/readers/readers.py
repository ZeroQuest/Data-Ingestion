import json
import logging
import os
import pandas as pd

logger = logging.getLogger(__name__)

def read_input(source):
    """
    Reads the source input based on the configuration
    Returns a pandas dataframe
    """

    if source["type"] == "csv":
        return read_csv(source)
    elif source["type"] == "json":
        return read_json(source)
    else:
        raise ValueError(f"Unsupported source type {source['type']}")


def read_csv(source):
    """
    Reads a .csv file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])
    logger.info(f"CSV file read from: {path}")

    try:
        return pd.read_csv(path)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"CSV file not found at path: {path}") from e
    except ValueError as e:
        raise ValueError(f"Failed to parse CSV at path: {path}") from e


def read_json(source):
    """
    Reads a .json file based on the path provided in the config
    Returns a pandas dataframe
    """
    path = os.path.join("..", source["path"])

    # Load the entire json file
    try:
        with open(path, "r") as file:
            data = json.load(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found at path: {path}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in file: {path}") from e

    # Get the root of a desired nested json based off the config
    root = source.get("json_root")

    if root:
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected top-level JSON object in {path}, "
                f"found {type(data).__name__}"
            )

        if root not in data:
            raise KeyError(f"json_root '{root}' not found in JSON file: {path}")

        # Gather the json metadata
        metadata = {key: value for key, value in data.items() if key != root}

        # Gather the nested data
        data = data[root]
    else:
        # Otherwise, metadata is empty
        metadata = {}

    # Validate extracted root data
    if not isinstance(data, (list, dict)):
        raise ValueError(
            f"JSON data must be a list or object, got " f"{type(data).__name__}"
        )

    # Create a dataframe based on the nested data
    try:
        df = pd.DataFrame(data)
    except Exception as e:
        raise ValueError(f"Failed to create DataFrame from JSON data in {path}") from e

    # Add the metadata to the dataframe
    for key, value in metadata.items():
        df[key] = value

    logger.info(f"JSON file read from: {path}")
    return df