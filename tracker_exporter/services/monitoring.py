# pylint: disable=W0102
import logging

from contextlib import contextmanager
from typing import Callable, ContextManager
from functools import wraps
from datadog import DogStatsd

from yandex_tracker_client.exceptions import (
    TrackerError,
    TrackerServerError,
    TrackerRequestError,
    TrackerClientError,
)

logger = logging.getLogger(__name__)


class DogStatsdClient:
    """This class represents interface for DataDog statsd UDP client."""

    def __init__(
        self,
        host: str,
        port: int,
        base_labels: list = [],  # pylint: disable=W0102
        metric_name_prefix: str = "tracker_exporter",
        use_ms: bool = True,
        enabled: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.base_labels = base_labels
        self.prefix = metric_name_prefix
        self._enabled = enabled
        self._use_ms = use_ms

        if self._enabled:
            assert self.host is not None
            assert self.port is not None

        self.client = DogStatsd(host=self.host, port=self.port, use_ms=self._use_ms, constant_tags=self.base_labels)

    def send_count_metric(self, name: str, value: int, tags: list = []) -> Callable:
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

    def send_gauge_metric(self, name: str, value: int, tags: list = []) -> None:
        if not self._enabled:
            return

        metric = f"{self.prefix}_{name}"
        self.client.gauge(metric, value, tags=tags)
        logger.debug(f"Success sent gauge metric: {metric}")

    @contextmanager
    def _dummy_send_time_metric(self):
        yield

    def send_time_metric(self, name: str, tags: list = [], **kwargs) -> Callable | ContextManager:
        metric = f"{self.prefix}_{name}"
        if self._enabled:
            return self.client.timed(metric, tags=tags, **kwargs)
        return self._dummy_send_time_metric()


def sentry_events_filter(event, hint):  # pylint: disable=R1710
    #  Drop all events without exception trace
    if "exc_info" not in hint:
        return

    exception = hint["exc_info"][1]
    if isinstance(exception, (TrackerError, TrackerClientError, TrackerRequestError, TrackerServerError)):
        event["fingerprint"] = ["tracker-error"]

    return event
