import os
import pytest

from tracker_exporter.config import Settings
from tracker_exporter.etl import YandexTrackerETL
from tracker_exporter.services.clickhouse import ClickhouseClient
from tracker_exporter.services.tracker import YandexTrackerClient

# Token & OrgID from Github
os.environ["EXPORTER_TRACKER__SEARCH__QUEUES"] = "OSSPYTEST"
os.environ["EXPORTER_CLICKHOUSE__ENABLE_UPLOAD"] = "false"


@pytest.fixture(scope="function")
def etl() -> YandexTrackerETL:
    """Returns YandexTrackerETL for tests."""
    return YandexTrackerETL(
        tracker_client=YandexTrackerClient(),
        clickhouse_client=ClickhouseClient(),
    )


@pytest.fixture(scope="function")
def config() -> Settings:
    return Settings()
