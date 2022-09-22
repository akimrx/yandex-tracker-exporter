# pylint: disable=W0102
import logging

from functools import wraps
from datadog import DogStatsd

from yandex_tracker_client.exceptions import (
    TrackerError,
    TrackerServerError,
    TrackerRequestError,
    TrackerClientError,
)
from tracker_exporter.defaults import (
    MONITORING_METRIC_BASE_PREFIX,
    MONITORING_HOST,
    MONITORING_PORT,
    MONITORING_BASE_LABELS,
    MONITORING_ENABLED
)

logger = logging.getLogger(__name__)


class DogStatsdClient:
    """This class represents interface for DataDog statsd UDP client."""

    def __init__(self,
                 host: str = MONITORING_HOST,
                 port: int = MONITORING_PORT,
                 base_labels: list = MONITORING_BASE_LABELS,  # pylint: disable=W0102
                 metric_name_prefix: str = MONITORING_METRIC_BASE_PREFIX,
                 use_ms: bool = True,
                 enabled: bool = MONITORING_ENABLED):

        self.host = host
        self.port = int(port)
        self.base_labels = base_labels
        self.prefix = metric_name_prefix
        self._enabled = enabled
        self.client = DogStatsd(
            host=self.host,
            port=self.port,
            use_ms=use_ms,
            constant_tags=self.base_labels
        )
        if self._enabled:
            assert self.host is not None
            assert self.port is not None
        logger.info(f"Monitoring send metrics is {'enabled' if self._enabled else 'disabled'}")

    def send_count_metric(self,
                          name: str,
                          value: int,
                          tags: list = []):
        metric = f"{self.prefix}_{name}"
        def metric_wrapper(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self._enabled:
                    return func(*args, **kwargs)
                self.client.increment(metric, value, tags=tags)
                logger.debug(f"Success sent count metric: {metric}")
                return func(*args, **kwargs)
            return wrapper
        return metric_wrapper

    def send_gauge_metric(self,
                          name: str,
                          value: int,
                          tags: list = []):
        if not self._enabled:
            return
        metric = f"{self.prefix}_{name}"
        self.client.gauge(metric, value, tags=tags)
        logger.debug(f"Success sent gauge metric: {metric}")

    def send_time_metric(self,
                         name: str,
                         tags: list = []):
        metric = f"{self.prefix}_{name}"
        def metric_wrapper(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self._enabled:
                    return func(*args, **kwargs)
                with self.client.timed(metric, tags=tags):
                    return func(*args, **kwargs)
            logger.debug(f"Success start time metric: {metric}")
            return wrapper
        return metric_wrapper


def sentry_events_filter(event, hint):  # pylint: disable=R1710
    #  Drop all events without exception trace
    if "exc_info" not in hint:
        return

    exception = hint["exc_info"][1]
    if isinstance(exception, (TrackerError, TrackerClientError, TrackerRequestError, TrackerServerError)):
        event["fingerprint"] = ["tracker-error"]

    return event
