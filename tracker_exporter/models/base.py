import json
from abc import ABCMeta, ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ClickhousePayload(BaseModel):
    issue: dict
    changelog: list
    metrics: list


class StateStorageTypes(str, Enum):
    redis = "redis"
    jsonfile = "jsonfile"
    custom = "custom"


class JsonStorageStrategies(str, Enum):
    local = "local"
    s3 = "s3"


class LogLevels(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class TrackerChangelogEvents:
    ISSUE_WORKFLOW = "IssueWorkflow"
    ISSUE_MOVED = "IssueMoved"


class TrackerWorkflowTypes:
    TRANSITION = "status"
    RESOLVE_ISSUE = "resolution"


class YandexTrackerLanguages(str, Enum):
    ru = "ru"
    en = "en"


class TimeDeltaOut:
    SECONDS = "seconds"
    MINUTES = "minutes"


class ClickhouseProto:
    HTTPS = "https"
    HTTP = "http"


class Base:
    """Base class for objects."""

    __metaclass__ = ABCMeta

    def __str__(self) -> str:
        return str(self.to_dict())

    def __repr__(self) -> str:
        return str(self)

    def __getitem__(self, item):
        return self.__dict__[item]

    @classmethod
    def de_json(cls, data) -> dict:
        """Deserialize object."""
        if not data:
            return None

        data = data.copy()
        return data

    def to_json(self) -> dict:
        """Serialize object to json."""
        return json.dumps(self.to_dict())

    def to_dict(self) -> dict:
        """Recursive serialize object."""

        def null_cleaner(value: Any):
            if value is None:
                return ""
            return value

        def parse(val):
            if isinstance(val, list):
                return [parse(it) for it in val]
            if isinstance(val, dict):
                return {key: null_cleaner(parse(value)) for key, value in val.items() if not key.startswith("_")}
            return val

        data = self.__dict__.copy()
        return parse(data)


class BaseStateStorage(ABC):
    """Abstract class for state storage.
    Allows you to save, receive, delete and flush the state.

    """

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Save key:value pair to storage."""

    @abstractmethod
    def get(self, key: str) -> Any:
        """Get value by key from storage."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete value by key from storage."""

    @abstractmethod
    def flush(self) -> None:
        """Flush (drop) state from storage."""


class JSONFileStorageStrategy(ABC):
    """Abstract strategy for store content via file."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    @abstractmethod
    def read(self) -> Any:
        """Read content from file."""

    @abstractmethod
    def save(self) -> Any:
        """Save content to file."""
