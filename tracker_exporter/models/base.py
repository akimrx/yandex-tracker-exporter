import json
from abc import ABCMeta
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ClickhousePayload(BaseModel):
    issue: dict
    changelog: list
    metrics: list


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
