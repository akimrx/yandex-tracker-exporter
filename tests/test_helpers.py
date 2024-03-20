import pytest
import tracker_exporter.utils.helpers as helpers

from tracker_exporter.config import Settings
from datetime import datetime
from contextlib import nullcontext as does_not_raise


class StringTestObject:
    def __init__(self):
        self.name = "stringTestObject"


class IntTestObject:
    def __init__(self):
        self.name = 1


@pytest.mark.parametrize(
    "end_time, start_time, unit, expected, expectation",
    [
        (
            datetime(2023, 1, 1, 10, 1, 0),
            datetime(2023, 1, 1, 10, 0, 0),
            helpers.TimeDeltaOut.SECONDS,
            60,
            does_not_raise()
        ),
        (
            datetime(2023, 1, 1, 10, 1, 0),
            datetime(2023, 1, 1, 10, 0, 0),
            helpers.TimeDeltaOut.MINUTES,
            1,
            does_not_raise()
        ),
        (
            "2023-01-01 10:01:00",
            "2023-01-01 10:00:00",
            helpers.TimeDeltaOut.MINUTES,
            1,
            pytest.raises(AssertionError)
        ),
    ]
)
def test_get_timedelta(end_time, start_time, unit, expected, expectation):
    with expectation:
        assert expected == helpers.get_timedelta(end_time, start_time, unit)


@pytest.mark.parametrize(
    "start_date, end_date, busdays_only, expected",
    [
        (
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 10, 30, 0),
            True,
            0
        ),
        (
            datetime(2023, 1, 1, 10, 0, 0),
            datetime(2023, 1, 1, 10, 30, 0),
            False,
            30 * 60
        ),
        (
            "2023-01-01 10:00:00",
            "2023-01-01 10:30:00",
            True,
            0
        ),
        (
            "2023-01-01 10:00:00",
            "2023-01-01 10:30:00",
            False,
            30 * 60
        ),
        (
            "2023-10-16 10:00:00",
            "2023-10-16 23:00:00",
            True,
            12 * 60 * 60
        ),
    ]
)
def test_calculate_time_spent(start_date, end_date, busdays_only, expected):
    assert expected == helpers.calculate_time_spent(start_date, end_date, busdays_only)


def test_fix_null_dates(config: Settings):
    data = {"a": "b"}
    for i in range(0, len(config.not_nullable_fields)):
        data[config.not_nullable_fields[i]] = None
        assert data[config.not_nullable_fields[i]] is None

    cleaned_data = helpers.fix_null_dates(data)
    assert data == cleaned_data


@pytest.mark.parametrize(
    "resource, attribute, low, expected",
    [
        (
            StringTestObject(),
            "name",
            True,
            "stringtestobject",
        ),
        (
            StringTestObject(),
            "name",
            False,
            "stringTestObject",
        ),
        (
            StringTestObject(),
            "age",
            False,
            None,
        ),
        (
            IntTestObject(),
            "name",
            True,
            1,
        ),
        (
            IntTestObject(),
            "age",
            False,
            None,
        ),
    ]
)
def test_validate_resource(resource, attribute, low, expected):
    assert expected == helpers.validate_resource(resource, attribute, low)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("русскаястрока", "русскаястрока"),
        ("РусскийВерблюд", "русский_верблюд"),
        ("русскийВерблюд2", "русский_верблюд_2"),
        ("Русские пробелы", "русские_пробелы"),
        ("русский-кебаб", "русский_кебаб"),
        ("РУССКИЕ_БОЛЬШИЕ", "русские_большие"),
        ("русская_змея", "русская_змея"),
        ("РусскийДлинныйВерблюдПлюсЧисло1", "русский_длинный_верблюд_плюс_число_1"),
        ("singlestring", "singlestring"),
        ("camelCase", "camel_case"),
        ("longCamelCase", "long_camel_case"),
        ("longCamelCaseWithNumber1", "long_camel_case_with_number_1"),
        ("PascalCase", "pascal_case"),
        ("LongPascalCase", "long_pascal_case"),
        ("LongPascalCaseWithNumber1", "long_pascal_case_with_number_1"),
        ("snake_case", "snake_case"),
        ("kebab-case", "kebab_case"),
        ("CONSTANT_CASE", "constant_case"),
        ("camelCase-kebab_snakePascalCaseCONSTANT_case", "camel_case_kebab_snake_pascal_case_constant_case"),
        ("separated string case", "separated_string_case"),
        (None, None),
        (" ", ""),
    ]
)
def test_to_snake_case(text, expected):
    assert expected == helpers.to_snake_case(text)


@pytest.mark.parametrize(
    "dtime, date_only, timezone, expected",
    [
        (
            "2023-01-01T10:00:00.123+0000",
            True,
            "UTC",
            "2023-01-01"
        ),
        (
            "2023-01-01T10:00:00.123+0300",
            False,
            "UTC",
            "2023-01-01T07:00:00.123"
        ),
        (
            "2023-01-01T10:00:00.123+0000",
            False,
            "Europe/Moscow",
            "2023-01-01T13:00:00.123"
        ),
        (
            None,
            False,
            "UTC",
            None
        ),
    ]
)
def test_convert_datetime(dtime, date_only, timezone, expected):
    assert expected == helpers.convert_datetime(dtime, date_only=date_only, timezone=timezone)


@pytest.mark.skip("Later")
def test_backoff(exceptions, base_delay, expo_factor, max_tries, jitter):
    pass


@pytest.mark.parametrize(
    "seconds, verbosity, expected",
    [
        (60, 2, "1m"),
        (300, 2, "5m"),
        (320, 2, "5m 20s"),
        (86700, 2, "1d 5m"),
        (3200400, 3, "1mo 1w 1h")
    ]
)
def test_to_human_time(seconds, verbosity, expected):
    assert expected == helpers.to_human_time(seconds, verbosity)


@pytest.mark.parametrize(
    "timestr, expected",
    [
        ("1m", 60),
        ("5m", 300),
        ("5m 20s", 320),
        ("1d 5m", 86700),
        ("1mo 1w 1h", 3200400),
    ]
)
def test_from_human_time(timestr, expected):
    assert expected == helpers.from_human_time(timestr)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("normalized", "normalized"),
        ("emoji😎", "emoji"),
    ]
)
def test_string_normalize(text, expected):
    assert expected == helpers.string_normalize(text)

