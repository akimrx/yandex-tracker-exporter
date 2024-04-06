"""This module contains content serializers."""

import json
import yaml

from abc import ABC, abstractmethod
from typing import Any

from tracker_exporter.exceptions import SerializerError


class AbstractSerializer(ABC):
    """
    An abstract serializer like JSON, YAML, etc.

    All (de)serialize errors must be raise `SerializerError`.
    """

    def __init__(self) -> None:
        self.is_initialized = True

    @property
    @abstractmethod
    def ext(self) -> str:
        """Abstract property for returns serializer file extension."""

    @abstractmethod
    def serialize(self, data: Any, *args, **kwargs) -> str:
        """Abstract method for serialize data."""

    @abstractmethod
    def deserialize(self, data: str, **kwargs) -> Any:
        """Abstract method for deserialize data."""


class JsonSerializer(AbstractSerializer):
    """
    Serializer for converting between JSON and Python objects.

    This serializer handles serialization (Python object to JSON format)
    and deserialization (JSON format to Python object) processes,
    ensuring that data is correctly transformed for JSON storage or
    retrieval while maintaining the Python object's structure.

    :raises SerializerError: If an error occurs during the JSON (de)serialization process.
    """

    @property
    def ext(self) -> str:
        return "json"

    def serialize(self, data: Any, ensure_ascii: bool = False, indent: int = 2, **kwargs) -> str:
        """
        Serialize data to JSON format (str).

        :param data: Data that will be serialized to JSON.
        :param ensure_ascii: If ``False``, then the return value can contain non-ASCII characters if they appear in strings contained in obj.
                             Otherwise, all such characters are escaped in JSON strings.
        :param indent: Spaces indent. Defaults: ``2``.

        :raises SerializerError: If an error occurs during the JSON serialization process.
        """
        try:
            return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent, **kwargs)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SerializerError(exc) from exc

    def deserialize(self, data: str, **kwargs) -> Any:
        """
        Derialize JSON data to Python object format.

        :param data: Data that will be deserialized from JSON.

        :raises SerializerError: If an error occurs during the JSON deserialization process.
        """
        try:
            return json.loads(data, **kwargs)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SerializerError(exc) from exc


__all__ = ["AbstractSerializer", "JsonSerializer"]
