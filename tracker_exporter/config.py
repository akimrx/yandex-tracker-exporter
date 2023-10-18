import datetime
import logging

from functools import lru_cache
from typing import List
from pydantic import validator, root_validator
from pydantic_settings import BaseSettings

from tracker_exporter.models.base import (
    YandexTrackerLanguages,
    LogLevels,
    StateStorageTypes,
    JsonStorageStrategies,
)
from tracker_exporter.exceptions import ConfigurationError
from tracker_exporter.services.monitoring import DogStatsdClient

YANDEX_TRACKER_API_SEARCH_HARD_LIMIT = 10000
YANDEX_TRACKER_HARD_LIMIT_ISSUE_URL = "https://github.com/yandex/yandex_tracker_client/issues/13"

logger = logging.getLogger(__name__)


class MonitoringSettings(BaseSettings):
    """Observability settings."""

    metrics_enabled: bool = False
    metrics_host: str = "localhost"
    metrics_port: int = 8125
    metrics_base_prefix: str = "tracker_exporter"
    metrics_base_labels: List[str] = []
    sentry_enabled: bool = False
    sentry_dsn: str | None = None

    @validator("sentry_dsn", pre=True, always=True)
    def validate_sentry_dsn(cls, value: str | None, values: dict) -> str:
        sentry_enabled = values.get("sentry_enabled")
        if sentry_enabled and not value:
            raise ConfigurationError("Sentry DSN must not be empty when Sentry is enabled")
        return value

    class Config:
        extra = "ignore"


class ClickhouseSettings(BaseSettings):
    """Settings for Clickhouse storage."""

    enable_upload: bool = True
    host: str = "localhost"
    proto: str = "http"
    port: int = 8123
    cacert_path: str | None = None
    serverless_proxy_id: str | None = None
    username: str = "default"
    password: str | None = None
    database: str = "agile"
    issues_table: str = "issues"
    issue_metrics_table: str = "issue_metrics"
    issues_changelog_table: str = "issues_changelog"
    auto_deduplicate: bool = True
    backoff_base_delay: int | float = 0.5
    backoff_expo_factor: int | float = 2.5
    backoff_max_tries: int = 3
    backoff_jitter: bool = True

    @validator("serverless_proxy_id", pre=True, always=True)
    def validate_serverless_proxy_id(cls, value: str | None, values: dict) -> str:
        http = values.get("proto") == "http"
        if http and value is not None:
            raise ConfigurationError("Clickhouse proto must be HTTPS when serverless used")
        return value

    @validator("cacert_path", pre=True, always=True)
    def validate_cacert_path(cls, value: str | None, values: dict) -> str:
        https = values.get("proto") == "https"
        if https and not value:
            raise ConfigurationError("CA cert path must not be empty when Clickhouse proto is HTTPS")
        return value

    class Config:
        extra = "ignore"


class IssuesSearchSettings(BaseSettings):
    """Settings for search & export."""

    query: str | None = None
    range: str = "2h"
    queues: str | List[str] | None = None
    per_page_limit: int = 100

    @validator("queues", pre=True, always=True)
    def validate_queues(cls, value: str) -> list:
        if value is None:
            return None

        if not isinstance(value, (str, list)):
            raise ConfigurationError("Invalid QUEUES. Example: TEST,TRASH. Received: %s", value)

        queues = value.split(",") if isinstance(value, str) else value
        return ", ".join([f"{q.upper()}" for q in queues])

    class Config:
        extra = "ignore"


class TrackerSettings(BaseSettings):
    """Settings for Yandex.Tracker client."""

    loglevel: LogLevels = LogLevels.warning
    token: str | None = None
    org_id: str | None = None
    iam_token: str | None = None
    cloud_org_id: str | None = None
    timeout: int = 10
    max_retries: int = 10
    language: YandexTrackerLanguages = YandexTrackerLanguages.en
    timezone: str = "Europe/Moscow"
    search: IssuesSearchSettings = IssuesSearchSettings()

    @root_validator(pre=True)
    def validate_tokens_and_orgs(cls, values) -> str:
        token = values.get("token")
        iam_token = values.get("iam_token")
        org_id = values.get("org_id")
        cloud_org_id = values.get("cloud_org_id")

        if all((token, iam_token)):
            raise ConfigurationError("Two tokens passed. Please use one of: TOKEN or IAM_TOKEN")
        elif not any((token, iam_token)):
            raise ConfigurationError("Empty tokens. Please use one of: TOKEN or IAM_TOKEN")

        if all((cloud_org_id, org_id)):
            raise ConfigurationError("Two orgs id passed. Please use one of: ORG_ID or CLOUD_ORG_ID")
        elif not any((cloud_org_id, org_id)):
            raise ConfigurationError("Empty orgs id. Please use one of: ORG_ID or CLOUD_ORG_ID")

        return values

    class Config:
        extra = "ignore"


class StateSettings(BaseSettings):
    """Settings for stateful mode."""

    storage: StateStorageTypes | None = StateStorageTypes.jsonfile
    redis_dsn: str = "redis://localhost:6379"
    jsonfile_strategy: JsonStorageStrategies = JsonStorageStrategies.local
    jsonfile_path: str = "./state.json"
    jsonfile_s3_bucket: str | None = None
    jsonfile_s3_region: str = "eu-east-1"
    jsonfile_s3_endpoint: str | None = None
    jsonfile_s3_access_key: str | None = None
    jsonfile_s3_secret_key: str | None = None
    custom_storage_params: dict = {}

    @root_validator(pre=True)
    def validate_state(cls, values) -> str:
        jsonfile_strategy = values.get("jsonfile_strategy")
        jsonfile_s3_bucket = values.get("jsonfile_s3_bucket")
        jsonfile_s3_endpoint = values.get("jsonfile_s3_endpoint")
        jsonfile_s3_access_key = values.get("jsonfile_s3_access_key")
        jsonfile_s3_secret_key = values.get("jsonfile_s3_secret_key")
        s3_is_configured = all(
            (
                jsonfile_s3_bucket,
                jsonfile_s3_endpoint,
                jsonfile_s3_access_key,
                jsonfile_s3_secret_key,
            )
        )

        if jsonfile_strategy == JsonStorageStrategies.s3 and not s3_is_configured:
            raise ConfigurationError("S3 must be configured for JSONFileStorage with S3 strategy.")

        return values

    class Config:
        extra = "ignore"


class Settings(BaseSettings):
    """Global merged config."""

    monitoring: MonitoringSettings = MonitoringSettings()
    clickhouse: ClickhouseSettings = ClickhouseSettings()
    tracker: TrackerSettings = TrackerSettings  # TODO (akimrx): research, called class not see TOKEN's
    state: StateSettings = StateSettings()
    stateful: bool = False
    stateful_initial_range: str = "1w"
    changelog_export_enabled: bool = True
    log_etl_stats: bool = True
    log_etl_stats_each_n_iter: int = 100

    loglevel: LogLevels = LogLevels.info
    workdays: List[int] = [0, 1, 2, 3, 4]
    business_hours_start: datetime.time = datetime.time(9)
    business_hours_end: datetime.time = datetime.time(22)
    datetime_response_format: str = "%Y-%m-%dT%H:%M:%S.%f%z"
    datetime_query_format: str = "%Y-%m-%d %H:%M:%S"
    datetime_clickhouse_format: str = "%Y-%m-%dT%H:%M:%S.%f"

    etl_interval_minutes: int = 30
    closed_issue_statuses: str | list = "closed,rejected,resolved,cancelled,released"
    not_nullable_fields: tuple | list | str = (
        "created_at",
        "resolved_at",
        "closed_at",
        "updated_at",
        "released_at",
        "deadline",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "moved_at",
    )

    @validator("closed_issue_statuses", pre=True, always=True)
    def validate_closed_issue_statuses(cls, value: str) -> list:
        if not isinstance(value, (str, list)):
            raise ConfigurationError(
                "Invalid CLOSED_ISSUES_STATUSES. Example: closed,released,cancelled. Received: %s",
                value,
            )

        if isinstance(value, str):
            return value.split(",")
        return value

    @validator("not_nullable_fields", pre=True, always=True)
    def validate_not_nullable_fields(cls, value: str) -> list:
        if not isinstance(value, (str, list, tuple)):
            raise ConfigurationError(
                "Invalid NOT_NULLABLE_FIELDS. Example: created_at,deadline,updated_at. Received: %s",
                value,
            )

        if isinstance(value, str):
            return value.split(",")
        return value

    class Config:
        env_prefix = "EXPORTER_"
        case_sensitive = False
        env_nested_delimiter = "__"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def _get_settings():
    cfg = Settings()
    return cfg


config = _get_settings()
monitoring = DogStatsdClient(
    host=config.monitoring.metrics_host,
    port=config.monitoring.metrics_port,
    base_labels=config.monitoring.metrics_base_labels,
    metric_name_prefix=config.monitoring.metrics_base_prefix,
    use_ms=True,
    enabled=config.monitoring.metrics_enabled,
)
