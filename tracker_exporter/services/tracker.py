import logging

from typing import List, Tuple
from yandex_tracker_client import TrackerClient
from yandex_tracker_client.collections import Issues, IssueComments

from tracker_exporter.models.issue import TrackerIssue
from tracker_exporter.models.enums import YandexTrackerLanguages
from tracker_exporter.utils.helpers import fix_null_dates
from tracker_exporter.services.monitoring import DogStatsdClient
from tracker_exporter.errors import TrackerError

logger = logging.getLogger(__name__)
monitoring = DogStatsdClient()


class YandexTrackerClient:
    """This class provide simple facade interface for Yandex.Tracker."""

    def __init__(self,
                 org_id: str,
                 token: str,
                 lang: YandexTrackerLanguages = YandexTrackerLanguages.EN):

        self.token = token
        self.org_id = str(org_id)
        self.lang = lang

        if self.lang.lower() not in ("en", "ru"):
            raise TrackerError("Tracker client language must be 'en' or 'ru'")

        self.client = TrackerClient(
            token=self.token,
            org_id=self.org_id,
            headers={"Accept-Language": self.lang}
        )

    def get_issue(self, issue_key: str) -> Issues:
        return self.client.issues[issue_key]

    def get_comments(self, issue_key: str) -> IssueComments:
        return self.client.issues[issue_key].comments.get_all()

    @monitoring.send_time_metric("issues_search_time_seconds")
    def search_issues(self, query: str, limit: int = 100) -> List[Issues]:
        found_issues = self.client.issues.find(query, per_page=limit)
        logger.info(f"Found {len(found_issues)} issues by query '{query}'")
        return found_issues

    @monitoring.send_time_metric("issue_transform_time_seconds")
    def issue_cycle_time(self, issue_key: str) -> Tuple[List[dict]]:
        issue = TrackerIssue(self.get_issue(issue_key))
        metrics = issue.metrics()

        if not metrics:
            return fix_null_dates(issue.to_dict()), None
        return fix_null_dates(issue.to_dict()), [m.to_dict() for m in metrics]
