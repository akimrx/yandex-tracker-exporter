import re
import time
import logging

from functools import wraps
from typing import Union, Tuple
from datetime import datetime

import holidays
import pandas as pd

from businesstime import BusinessTime
from tracker_exporter.models.enums import TimeDeltaOut
from tracker_exporter.defaults import (
    NOT_NULLABLE_FIELDS,
    WEEKENDS,
    BUSINESS_HOURS_START,
    BUSINESS_HOURS_END,
    TRACKER_DEFAULT_DATETIME_FORMAT
)

logger = logging.getLogger(__name__)


def get_timedelta(end_time: datetime,
                  start_time: datetime,
                  out: TimeDeltaOut = TimeDeltaOut.SECONDS) -> int:
    """Simple timedelta between dates."""
    assert isinstance(start_time, datetime)
    assert isinstance(end_time, datetime)

    delta = int((end_time - start_time).total_seconds())
    if out == TimeDeltaOut.MINUTES:
        return delta // 60
    if out == TimeDeltaOut.SECONDS:
        return delta
    return delta


def calculate_time_spent(start_date: datetime,
                         end_date: datetime,
                         busdays_only: bool = False,
                         weekends: Tuple[int] = WEEKENDS,
                         business_hours: Tuple = (BUSINESS_HOURS_START, BUSINESS_HOURS_END,)) -> int:
    """
    Calculate timedelta between dates with business days support.
    Weekdays: Monday is 0, Sunday is 6, so weekends (5, 6) mean (Sat, Sun).
    """
    if not isinstance(start_date, datetime):
        start_date = pd.to_datetime(start_date)
    if not isinstance(end_date, datetime):
        end_date = pd.to_datetime(end_date)

    if busdays_only:
        bt = BusinessTime(business_hours=business_hours, weekends=weekends, holidays=holidays.RU())  # pylint: disable=C0103
        result = bt.businesstimedelta(start_date, end_date).total_seconds()
    else:
        result = (end_date - start_date).total_seconds()

    return abs(int(result))


def fix_null_dates(data: dict) -> dict:
    to_remove = []

    for key, value in data.items():
        if key in NOT_NULLABLE_FIELDS and (value is None or value == ""):
            to_remove.append(key)

    for key in to_remove:
        del data[key]

    return data


# pylint: disable=R1710
def validate_resource(resource: object,
                      attribute: str,
                      low: bool = True) -> Union[str, list, bool, int, None]:
    """Validate Yandex.Tracker object attribute and return it if exists as string."""
    if hasattr(resource, attribute):
        _attr = getattr(resource, attribute)
        if isinstance(_attr, str):
            if low:
                return _attr.lower()
            return _attr
        return _attr


def to_snake_case(text: str) -> str:
    """Convert any string to `snake_case` format."""
    if text is None or text == "":
        return text

    text = re.sub(r"('|\")", "", text)
    string = re.sub(r"(_|-)+", " ", text).title().replace(" ", "")
    output = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', output).lower()


def to_simple_datetime(dtime: str,
                       source_dt_format: str = TRACKER_DEFAULT_DATETIME_FORMAT,
                       date_only: bool = False,
                       shift: int = 3) -> str:
    """Return (Unicode) date format `YYYY-MM-DD HH:mm:ss` or `YYYY-MM-DD` if `date_only`."""
    if dtime is None:
        logger.debug("dtime is empty, can't transform date to simple string.")
        return

    if date_only:
        fmt = "%Y-%m-%d"
    else:
        fmt = "%Y-%m-%d %H:%M:%S"

    timestamp = time.mktime(datetime.strptime(dtime.split(".")[0], source_dt_format).timetuple())
    if shift > 0:
        timestamp += 60 * 60 * shift
    elif shift < 0:
        timestamp -= 60 * 60 * shift
    return datetime.fromtimestamp(int(timestamp)).strftime(fmt)


def retry(exceptions: tuple, tries: int = 3, delay: Union[float, int] = 1, backoff: int = 3):
    """Decorator to retry the execution of the func, if you have received the errors listed."""
    def retry_decorator(func):
        @wraps(func)
        def func_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            counter = 0
            while mtries > 0:
                try:
                    counter += 1
                    return func(*args, **kwargs)
                except exceptions as err:
                    mtries -= 1
                    if mtries == 0:
                        logger.warning(f"{func.__name__} has failed {counter} times")
                        raise err
                    logger.warning(
                        f"Error in func {func.__name__}, cause: {err}. "
                        f"Retrying ({counter}) in {mdelay} seconds..."
                    )
                    time.sleep(mdelay)
                    mdelay *= backoff
        return func_retry
    return retry_decorator


def to_human_time(seconds: Union[int, float], verbosity: int = 2) -> str:
    """Convert seconds to human readable timedelta
    like a `2w 3d 1h 20m`
    """
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


def string_normalize(text: str) -> str:
    """Remove all incompatible symbols."""
    emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                            "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r"", text)
