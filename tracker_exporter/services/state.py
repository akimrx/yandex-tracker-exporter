import os
import json
import logging

from typing import Any, Dict
from tracker_exporter.models.base import BaseStateStorage, JSONFileStorageStrategy
from tracker_exporter.exceptions import JsonFileNotFound, InvalidJsonFormat

logger = logging.getLogger(__name__)


class S3FileStorageStrategy(JSONFileStorageStrategy):
    """Strategy for storing a JSON file in the remote object storage (S3)."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        raise NotImplementedError  # TODO (akimrx): implement


class LocalFileStorageStrategy(JSONFileStorageStrategy):
    """Strategy for storing a JSON file in the local file system."""

    def __init__(self, file_path: str, raise_if_not_exists: bool = False):
        self.file_path = file_path
        self.raise_if_not_exists = raise_if_not_exists

        if not file_path.endswith(".json"):
            self.file_path = f"{file_path}.json"
        else:
            self.file_path = file_path

    def save(self, content: Any) -> None:
        """Save content to JSON file."""
        with open(self.file_path, "w", encoding="utf-8") as json_file:
            logger.debug(f"Dumping state to file {self.file_path} ...")
            json.dump(content, json_file, ensure_ascii=False, indent=2)
        logger.info(f"State successfuly saved to file: {self.file_path}")

    def read(self) -> Dict[str, Any]:
        """Read content from JSON file."""
        logger.info(f"Trying reading state from file {self.file_path}")
        if not all((os.path.isfile(self.file_path), os.path.exists(self.file_path))):
            if self.raise_if_not_exists:
                raise JsonFileNotFound("JSON file %s not found", self.file_path)
            logger.warning(f"State file with name '{self.file_path}' not found")
            return {}

        with open(self.file_path, "r", encoding="utf-8") as json_file:
            try:
                logger.debug(f"Trying opening file: {self.file_path}")
                content = json.load(json_file)
            except json.JSONDecodeError as exc:
                logger.exception(f"Invalid state file format: {exc}")
                raise InvalidJsonFormat(self.file_path)

        if not content or content is None:
            return {}
        return content


class JsonStateStorage(BaseStateStorage):
    """File storage backend based on JSON."""

    def __init__(self, strategy: JSONFileStorageStrategy) -> None:
        self.file_storage = strategy
        self.state = {}

    def get(self, key: str) -> Any:
        """Get state by key."""
        self.state = self.file_storage.read()
        return self.state.get(key)

    def set(self, key: str, value: str) -> None:
        """Set state as key=value."""
        self.state = self.file_storage.read()
        self.state[key] = value
        self.file_storage.save(self.state)

    def delete(self, key: str) -> None:
        """Delete state by key."""
        self.state = self.file_storage.read()
        if self.state.get(key) is not None:
            del self.state[key]
            self.file_storage.save(self.state)

    def flush(self):
        """Drop all states."""
        self.state = {}
        self.file_storage.save(self.state)


class RedisStateStorage(BaseStateStorage):
    """Redis storage backend. Supports retries with exponential backoff."""

    def __init__(self, host: str, port: str):
        self.host = host
        self.port = port
        raise NotImplementedError  # TODO (akimrx): implement


class StateKeeper:
    """Class for operations with state."""

    def __init__(self, storage: BaseStateStorage) -> None:
        self.storage = storage

    def get(self, key: str) -> Any:
        """Get state by key."""
        return self.storage.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set state by key:value pair."""
        return self.storage.set(key, value)

    def delete(self, key: str) -> None:
        """Delete state by key."""
        return self.storage.delete(key)

    def flush(self) -> None:
        """Flush all keys in the state storage."""
        return self.storage.flush()
