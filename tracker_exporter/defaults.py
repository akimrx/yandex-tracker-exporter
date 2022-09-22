import os
import datetime as dt

# Common settings
LOGLEVEL = os.environ.get("EXPORTER_LOGLEVEL", "info")
UPLOAD_TO_STORAGE = os.environ.get("EXPORTER_ENABLE_UPLOAD", "false").lower() in ("true", "yes")

# Business days settings
BUSINESS_HOURS_START = dt.time(9)
BUSINESS_HOURS_END = dt.time(22)
WEEKENDS = (5, 6,)  # Monday is 0, Sunday is 6

# Monitoring settings
MONITORING_ENABLED = os.environ.get("EXPORTER_MONITORING_ENABLED", "false").lower() in ("true", "yes")
MONITORING_HOST = os.environ.get("EXPORTER_MONITORING_HOST", "localhost")
MONITORING_PORT = os.environ.get("EXPORTER_MONITORING_PORT", 8125)
MONITORING_METRIC_BASE_PREFIX = os.environ.get("MONITORING_METRIC_PREFIX", "tracker_exporter")
MONITORING_BASE_LABELS = [
    "project:internal",
]
SENTRY_ENABLED = os.environ.get("EXPORTER_SENTRY_ENABLED", "false").lower() in ("true", "yes")
SENTRY_DSN = os.environ.get("EXPORTER_SENTRY_DSN")

# Tracker settings
TRACKER_DEFAULT_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
TRACKER_BULK_CYCLE_TIME_ISSUES_LIMIT = 1000
TRACKER_TOKEN = os.environ.get("EXPORTER_TRACKER_TOKEN")
TRACKER_ORG_ID = os.environ.get("EXPORTER_TRACKER_ORG_ID")
TRACKER_ISSUES_UPDATE_INTERVAL = os.environ.get("EXPORTER_TRACKER_ISSUES_FETCH_INTERVAL", 30)  # min
TRACKER_ISSUES_SEARCH_QUERY = os.environ.get("EXPORTER_TRACKER_ISSUES_SEARCH_QUERY")
TRACKER_ISSUES_SEARCH_RANGE = os.environ.get("EXPORTER_TRACKER_ISSUES_SEARCH_RANGE", "2h")

# Clickhouse settings
CLICKHOUSE_HOST = os.environ.get("EXPORTER_CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PROTO = os.environ.get("EXPORTER_CLICKHOUSE_PROTO", "http")
CLICKHOUSE_HTTP_PORT = os.environ.get("EXPORTER_CLICKHOUSE_HTTP_PORT", 8123)
CLICKHOUSE_CACERT_PATH = os.environ.get("EXPORTER_CLICKHOUSE_CERT", None)
CLICKHOUSE_SERVERLESS_PROXY_ID = os.environ.get("EXPORTER_CLICKHOUSE_SERVERLESS_PROXY_ID", None)
CLICKHOUSE_USER = os.environ.get("EXPORTER_CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("EXPORTER_CLICKHOUSE_PASSWORD")
CLICKHOUSE_DATABASE = os.environ.get("EXPORTER_CLICKHOUSE_DATABASE", "agile")
CLICKHOUSE_ISSUES_TABLE = os.environ.get("EXPORTER_CLICKHOUSE_ISSUES_TABLE", "issues")
CLICKHOUSE_ISSUE_METRICS_TABLE = os.environ.get("EXPORTER_CLICKHOUSE_ISSUE_METRICS_TABLE", "issue_metrics")

# Exporter settings
_DEFAULT_CLOSED_ISSUE_STATUSES = "closed,rejected,resolved,cancelled,released"
CLOSED_ISSUE_STATUSES = os.environ.get("EXPORTER_CLOSED_ISSUE_STATUES", _DEFAULT_CLOSED_ISSUE_STATUSES).split(",")
EXCLUDE_QUEUES = (
    "TEST",
)
NOT_NULLABLE_FIELDS = (
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
)
