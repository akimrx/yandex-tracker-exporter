import os
import time
import pytest
from tracker_exporter.etl import YandexTrackerETL

NEW_ISSUE = None


@pytest.mark.skip("Later")
def test_prepare_issue(etl: YandexTrackerETL):
    global NEW_ISSUE
    n = str(time.time()).split(".")[0]
    new_issue = etl.tracker.client.issues.create(queue="OSSPYTEST", summary=f"TEST-{n}")
    NEW_ISSUE = new_issue.key
    # os.environ["EXPORTER_TRACKER__SEARCH_QUERY"] = f"Issue: {new_issue.key}"
    # time.sleep(5)
    # etl.tracker.client.issues[new_issue.key]  # todo status change to In Progress
    # time.sleep(5)


def test_query_builder(etl: YandexTrackerETL):
    pass


def test_issue_transform(etl: YandexTrackerETL):
    pass


def test_export_and_transform(etl: YandexTrackerETL):
    pass


def test_upload_to_storage(etl: YandexTrackerETL):
    pass


def test_full_run(etl: YandexTrackerETL):
    pass
