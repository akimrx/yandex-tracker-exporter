import re
import os
import time
import json
import logging
import random
import pytz
import psutil

from functools import wraps
from typing import Union, Tuple, Type, Callable, Any
from datetime import datetime, timezone as dt_timezone

import holidays
import pandas as pd
import businesstimedelta


from yandex_tracker_client.objects import Reference
from tracker_exporter._typing import DateTimeISO8601Str, DateStr, _Sequence
from tracker_exporter.models.base import TimeDeltaOut
from tracker_exporter.config import config

logger = logging.getLogger(__name__)


def get_timedelta(end_time: datetime, start_time: datetime, out: TimeDeltaOut = TimeDeltaOut.SECONDS) -> int:
    """Simple timedelta between dates."""
    assert isinstance(start_time, datetime)
    assert isinstance(end_time, datetime)

    delta = int((end_time - start_time).total_seconds())
    if out == TimeDeltaOut.MINUTES:
        return delta // 60
    if out == TimeDeltaOut.SECONDS:
        return delta
    return delta


def calculate_time_spent(
    start_date: datetime,
    end_date: datetime,
    busdays_only: bool = False,
    workdays: list = config.workdays,
    business_hours: Tuple = (
        config.business_hours_start,
        config.business_hours_end,
    ),
) -> int:
    """
    Calculate timedelta between dates with business days support.
    Weekdays: Monday is 0, Sunday is 6, so weekends (5, 6) mean (Sat, Sun).
    Returns: seconds
    """
    if not isinstance(start_date, datetime):
        start_date = pd.to_datetime(start_date)
    if not isinstance(end_date, datetime):
        end_date = pd.to_datetime(end_date)

    holiday_rules = businesstimedelta.HolidayRule(holidays.RU())
    workday_rules = businesstimedelta.WorkDayRule(
        start_time=business_hours[0], end_time=business_hours[1], working_days=workdays
    )

    if busdays_only:
        logger.debug(f"Calculating workhours. Business hours: {business_hours}. {start_date}, {end_date}")
        bt = businesstimedelta.Rules([workday_rules, holiday_rules])
        result = bt.difference(start_date, end_date).timedelta.total_seconds()
    else:
        logger.debug("Calculating regular hours")
        result = (end_date - start_date).total_seconds()

    return abs(int(result))


def fix_null_dates(data: dict) -> dict:
    """Clean keys with None values from dict."""
    to_remove = []

    for key, value in data.items():
        if key in config.not_nullable_fields and (value is None or value == ""):
            to_remove.append(key)

    for key in to_remove:
        del data[key]

    return data


# pylint: disable=R1710
def validate_resource(resource: object, attribute: str, low: bool = True) -> Any | None:
    """Validate Yandex.Tracker object attribute and return it if exists."""
    if hasattr(resource, attribute):
        _attr = getattr(resource, attribute)
        if isinstance(_attr, str):
            if low:
                return _attr.lower()
            return _attr
        return _attr


def to_snake_case(text: str) -> str:
    """Convert any string to `snake_case` format."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError(f"Expected string, received: {type(text)}")
    if text.strip() == "":
        return text.strip()

    text = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", text)
    text = re.sub(r"(?<=[a-z])(?=\d)", "_", text)
    text = re.sub(r"(?<=\d)(?=[a-z])", "_", text)
    text = re.sub(r"[^a-zA-Z0-9_]", "_", text)

    return text.lower()


def convert_datetime(
    dtime: str,
    source_dt_format: str = config.datetime_response_format,
    output_format: str = config.datetime_clickhouse_format,
    date_only: bool = False,
    timezone: str = "UTC",
) -> DateTimeISO8601Str | DateStr:
    """
    Returns ISO8601 datetime (UTC).
    Or date format `YYYY-MM-DD` from original datetime when date_only passed.
    """
    logger.debug(f"Timezone set to {timezone}")
    if dtime is None:
        return None

    dt = datetime.strptime(dtime, source_dt_format)
    if dt.tzinfo is None:
        logger.debug("Replacing datetime tzinfo to UTC")
        dt = dt.replace(tzinfo=dt_timezone.utc)

    output_datetime = dt.astimezone(pytz.timezone(timezone))
    if date_only:
        return output_datetime.date().strftime("%Y-%d-%m")

    if output_format.endswith("%f"):
        return output_datetime.strftime(output_format)[:-3]
    return output_datetime.strftime(output_format)


def backoff(
    exceptions: _Sequence[Type[Exception]],
    base_delay: int | float = 0.5,
    expo_factor: int | float = 2.5,
    max_tries: int = 3,
    jitter: bool = False,
) -> Callable:
    """Decorator for backoff retry function/method calls."""

    def retry_decorator(func: Callable):
        @wraps(func)
        def func_retry(*args, **kwargs):
            logger.debug(f"Start func {func.__qualname__} with {max_tries} tries")
            tries, delay = max_tries, base_delay
            counter = 0
            while tries > 0:
                try:
                    counter += 1
                    return func(*args, **kwargs)
                except exceptions as err:
                    tries -= 1
                    if tries == 0:
                        logger.error(f"{func.__qualname__} has failed {counter} times")
                        raise
                    logger.warning(
                        f"Error in func {func.__qualname__}, cause: {err}. "
                        f"Retrying ({counter}/{max_tries - 1}) in {delay:.2f}s..."
                    )
                    if jitter:
                        delay = random.uniform(delay / 2, delay * expo_factor)  # nosec
                        time.sleep(delay)
                    else:
                        time.sleep(delay)
                    delay *= expo_factor

        return func_retry

    return retry_decorator


def to_human_time(seconds: Union[int, float], verbosity: int = 2) -> str:
    """Convert seconds to human readable timedelta like a `2w 3d 1h 20m`."""
    seconds = int(seconds)
    if seconds == 0:
        return "0s"

    negative = False
    if seconds < 0:
        negative = True
        seconds = abs(seconds)

    result = []
    intervals = (
        ("y", 31104000),
        ("mo", 2592000),
        ("w", 604800),
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    )
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            result.append(f"{value}{name}")
    delta = " ".join(result[:verbosity])
    return f"-{delta}" if negative else delta


def from_human_time(timestr: str) -> int:
    """Convert a duration string like `2w 3d 1h 20m` to seconds."""

    logger.debug(f"Received human time: {timestr}")
    total_seconds = 0
    patterns = [
        (r"(\d+)y", 365 * 24 * 60 * 60),  # years
        (r"(\d+)mo", 30 * 24 * 60 * 60),  # months
        (r"(\d+)w", 7 * 24 * 60 * 60),  # weeks
        (r"(\d+)d", 24 * 60 * 60),  # days
        (r"(\d+)h", 60 * 60),  # hours
        (r"(\d+)m", 60),  # minutes
        (r"(\d+)s", 1),  # seconds
    ]

    for pattern, multiplier in patterns:
        matches = re.search(pattern, timestr)
        if matches:
            total_seconds += int(matches.group(1)) * multiplier
            timestr = re.sub(pattern, "", timestr)

    timestr = timestr.strip()
    if timestr:
        raise ValueError(f"Invalid format detected in the string: '{timestr}'")

    return total_seconds


def string_normalize(text: str) -> str:
    """Remove all incompatible symbols."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


def extract_changelog_field(value: Any) -> Any:
    """Extractor for Yandex.Tracker issue changelog."""
    match value:
        case list():
            logger.debug(f"Changelog field is list: {value}")
            return ", ".join(extract_changelog_field(i) for i in value)
        case str():
            logger.debug(f"Changelog field is string: {value}")
            try:
                dtime = convert_datetime(value)
            except Exception:
                if len(value) > 100:
                    return "text too long, see history in UI"
                return value
            else:
                return dtime
        case dict():
            logger.debug(f"Changelog field is dict, dumping: {value}")
            return json.dumps(value, ensure_ascii=False)
        case None:
            logger.debug(f"Changelog field is None, fixing: {value}")
            return ""
        case int():
            logger.debug(f"Changelog field is integer: {value}")
            return str(value)
        case float():
            logger.debug(f"Changelog field is float: {value}")
            return str(value)
        case Reference():
            logger.debug(f"Changelog field is Reference to object: {value}. Extracting...")
            return (
                validate_resource(value, "key", low=False)
                or validate_resource(value, "email")
                or validate_resource(value, "name", low=False)
                or validate_resource(value, "id", low=False)
            )
        case _:
            logger.warning(f"Unknown type of changelog field received: {type(value)}: {value}")


def bytes_to_human(data: int, granularity=2):
    """Convert bytes to human format with binary prefix."""
    _bytes = int(data)
    result = []
    sizes = (  # fmt: off
        ("TB", 1024**4),
        ("GB", 1024**3),
        ("MB", 1024**2),
        ("KB", 1024),
        ("B", 1),
    )  # fmt: on
    if _bytes == 0:
        return 0
    else:
        for name, count in sizes:
            value = _bytes // count
            if value:
                _bytes -= value * count
                result.append(f"{value}{name}")
        return ", ".join(result[:granularity])


def log_etl_stats(iteration: int, remaining: int, elapsed: float, entity: str = "issues"):  # pragma: no cover
    """Logging resources usage."""
    process = psutil.Process(os.getpid())
    memory = process.memory_info()
    memory_rss_usage = bytes_to_human(memory.rss, granularity=1)
    elapsed_time = to_human_time(elapsed)

    try:
        avg_time = elapsed // iteration
        avg_task_transform = f"{avg_time:.2f}ms" if avg_time < 1 else to_human_time(avg_time)
    except ZeroDivisionError:
        avg_task_transform = "calculating.."

    logger.info(
        f"Processed {iteration} of ~{remaining} {entity}. Avg time per issue: {avg_task_transform}. "
        f"Elapsed time: {elapsed_time}. MEM_RSS_USED: {memory_rss_usage}"
    )
