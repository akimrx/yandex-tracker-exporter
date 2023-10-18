import logging

from typing import List
from yandex_tracker_client import TrackerClient
from yandex_tracker_client.collections import Issues, IssueComments

from tracker_exporter.models.base import YandexTrackerLanguages
from tracker_exporter.config import (
    config,
    monitoring,
    YANDEX_TRACKER_API_SEARCH_HARD_LIMIT,
    YANDEX_TRACKER_HARD_LIMIT_ISSUE_URL,
)

logger = logging.getLogger(__name__)


class YandexTrackerClient:
    """This class provide simple wrapper over default Yandex.Tracker client."""

    def __init__(
        self,
        *,
        token: str | None = config.tracker.token,
        iam_token: str | None = config.tracker.iam_token,
        org_id: str | None = config.tracker.org_id,
        cloud_org_id: str | None = config.tracker.cloud_org_id,
        timeout: int = config.tracker.timeout,
        retries: int = config.tracker.max_retries,
        lang: YandexTrackerLanguages = config.tracker.language,
    ) -> None:
        self.client = TrackerClient(
            token=token,
            iam_token=iam_token,
            org_id=org_id,
            cloud_org_id=cloud_org_id,
            timeout=timeout,
            retries=retries,
            headers={"Accept-Language": lang},
        )

    @monitoring.send_time_metric("issue_prefetch_seconds")
    def get_issue(self, issue_key: str) -> Issues:
        return self.client.issues[issue_key]

    @monitoring.send_time_metric("comments_fetch_seconds")
    def get_comments(self, issue_key: str) -> IssueComments:
        return self.client.issues[issue_key].comments.get_all()

    @monitoring.send_time_metric("issues_search_time_seconds")
    def search_issues(
        self,
        query: str | None = None,
        filter: dict | list | None = None,
        order: dict | list | None = None,
        limit: int = 100,
    ) -> List[Issues]:
        # https://github.com/yandex/yandex_tracker_client/issues/13
        issues_count = self.client.issues.find(query=query, filter=filter, order=order, count_only=True)
        if issues_count > YANDEX_TRACKER_API_SEARCH_HARD_LIMIT:
            logger.warning(
                f"The number of tasks found ({issues_count}) exceeds the hard limit "
                f"({YANDEX_TRACKER_API_SEARCH_HARD_LIMIT}) of the Yandex.Tracker API. "
                f"Issue on Github - {YANDEX_TRACKER_HARD_LIMIT_ISSUE_URL}"
            )
        logger.info(f"Found {issues_count} issues by query: {query} | filter: {filter} | order: {order}'")
        return self.client.issues.find(query=query, filter=filter, order=order, per_page=limit)
