import time
import logging

from typing import Union, Tuple, List
from tracker_exporter.services.tracker import YandexTrackerClient
from tracker_exporter.services.clickhouse import ClickhouseClient
from tracker_exporter.services.monitoring import DogStatsdClient
from tracker_exporter.utils.helpers import to_human_time
from tracker_exporter.defaults import (
    CLICKHOUSE_HOST,
    CLICKHOUSE_HTTP_PORT,
    CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_DATABASE,
    CLICKHOUSE_ISSUES_TABLE,
    CLICKHOUSE_ISSUE_METRICS_TABLE,
    TRACKER_BULK_CYCLE_TIME_ISSUES_LIMIT,
    EXCLUDE_QUEUES,
    MONITORING_ENABLED,
    TRACKER_ORG_ID,
    TRACKER_TOKEN,
    TRACKER_ISSUES_SEARCH_RANGE,
    TRACKER_ISSUES_SEARCH_QUERY
)

logger = logging.getLogger(__name__)
tracker = YandexTrackerClient(token=TRACKER_TOKEN, org_id=TRACKER_ORG_ID)
monitoring = DogStatsdClient(enabled=MONITORING_ENABLED)


class Exporter:
    # TODO: configure class instance
    # TODO: parse migration from sprint to sprint by changelog (field changed),
    # by default exported only last sprint (tracker logic)
    def __init__(self):
        self.clickhouse = ClickhouseClient(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_HTTP_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD
        )

    @monitoring.send_time_metric("issues_processing_time_seconds")
    def _bulk_issue_cycle_time(self,
                               query: str,
                               limit: int = 50) -> Tuple[List]:
        """Collects and transforms metrics for found tasks."""
        issues = []
        metrics = []
        issues_without_metrics = 0
        found_issues = tracker.search_issues(query=query, limit=limit)
        logger.info("Prepare cycle time metrics...")

        for tracker_issue in found_issues:
            try:
                issue, metric = tracker.issue_cycle_time(tracker_issue.key)
                if metric is None:
                    logger.debug(f"Ignore {tracker_issue.key} because metrics is empty")
                    issues_without_metrics += 1
                    issues.append(issue)
                else:
                    issues.append(issue)
                    for m in metric:  # pylint: disable=C0103
                        metrics.append(m)
            except Exception as exc:
                logger.exception(f"Issue {tracker_issue.key} can't be transformed, details: {exc}")

        monitoring.send_gauge_metric("issues_without_metrics", value=issues_without_metrics)
        logger.info(
            f"Total issues: {len(issues)}, total cycle time metrics: {len(metrics)}, "
            f"ignored issues with empty metrics: {issues_without_metrics}"
        )
        return issues, metrics


    def _upload_data_to_storage(self, payload: list, table: str) -> None:
        """Inserts a batch of data into the Clickhouse with deduplication."""
        logger.info(f"Inserting batch ({len(payload)} rows) to Clickhouse ({table})...")
        self.clickhouse.insert_batch(CLICKHOUSE_DATABASE, table, payload)

        logger.info(f"Optimizing table '{table}' for deduplication...")
        self.clickhouse.deduplicate(CLICKHOUSE_DATABASE, table)


    @monitoring.send_time_metric("cycle_time_total_processing_time_seconds")
    def cycle_time(self,
                   query: str = TRACKER_ISSUES_SEARCH_QUERY,
                   exclude_queues: Union[list, tuple] = EXCLUDE_QUEUES,
                   search_range: str = TRACKER_ISSUES_SEARCH_RANGE,
                   upload: bool = True) -> int:
        """Export issues cycle time and upload its to storage."""
        logger.info("Started processing issues...")
        if query:
            logger.warning("Arguments `excluded_queues`, `search_range` has no effect if a `query` is passed")
        queues = ", ".join([f"!{q}" for q in exclude_queues])
        _default_query = f"Queue: {queues} AND Updated: >= now() - {search_range}"
        search_query = TRACKER_ISSUES_SEARCH_QUERY or _default_query
        start_time = time.time()

        issues, metrics = self._bulk_issue_cycle_time(
            search_query,
            limit=TRACKER_BULK_CYCLE_TIME_ISSUES_LIMIT
        )

        if upload:
            self._upload_data_to_storage(issues, table=CLICKHOUSE_ISSUES_TABLE)
            self._upload_data_to_storage(metrics, table=CLICKHOUSE_ISSUE_METRICS_TABLE)
        else:
            logger.debug("Upload to Clickhouse is disabled")

        elapsed_time = time.time() - start_time
        logger.info(
            f"Processing issues completed. Elapsed time: {to_human_time(elapsed_time)}, "
            f"total tasks processed: {len(issues)}"
        )

        return len(issues) if upload else 0
