import time
import logging
from datetime import datetime, timedelta
from typing import Tuple, List
from yandex_tracker_client.collections import Issues
from yandex_tracker_client.objects import SeekablePaginatedList
from yandex_tracker_client.exceptions import Forbidden

from tracker_exporter.config import config, monitoring
from tracker_exporter.models.issue import TrackerIssue
from tracker_exporter.models.base import ClickhousePayload
from tracker_exporter.services.state import StateKeeper
from tracker_exporter.services.tracker import YandexTrackerClient
from tracker_exporter.services.clickhouse import ClickhouseClient
from tracker_exporter.exceptions import ConfigurationError, UploadError, ExportOrTransformError
from tracker_exporter.utils.helpers import (
    fix_null_dates,
    from_human_time,
    convert_datetime,
    log_etl_stats,
)

logger = logging.getLogger(__name__)


class YandexTrackerETL:
    """Export, transform, load facade."""

    def __init__(
        self,
        *,
        tracker_client: YandexTrackerClient,
        clickhouse_client: ClickhouseClient,
        statekeeper: StateKeeper | None = None,
        database: str = config.clickhouse.database,
        issues_table: str = config.clickhouse.issues_table,
        metrics_table: str = config.clickhouse.issue_metrics_table,
        changelogs_table: str = config.clickhouse.issues_changelog_table,
        upload_to_storage: bool = config.clickhouse.enable_upload,
        state_key: str = "tracker_etl_default",
    ) -> None:
        self.tracker = tracker_client
        self.clickhouse = clickhouse_client
        self.state = statekeeper
        self.database = database
        self.issues_table = issues_table
        self.metrics_table = metrics_table
        self.changelogs_table = changelogs_table
        self.upload_to_storage = upload_to_storage
        self.state_key = state_key

    def _get_possible_new_state(self, issue: TrackerIssue | ClickhousePayload):
        try:
            last_state = issue.updated_at
        except AttributeError:
            last_state = issue.issue.updated_at
        return convert_datetime(
            last_state,
            source_dt_format=config.datetime_clickhouse_format,
            output_format=config.datetime_query_format,
            timezone=config.tracker.timezone,
        )

    def _build_search_query(
        self,
        stateful: bool = False,
        queues: str | None = None,
        search_query: str | None = None,
        search_range: str | None = None,
    ) -> str | dict:
        """Prepare search query for Yandex.Tracker."""
        default_order = ["updated"]
        sort_by_updated_asc = ' "Sort by": Updated ASC'

        def append_sort_by(query: str, sort_by: str) -> str:
            return f"{query} {sort_by}" if "ort by" not in query else query

        def build_stateful_query() -> str:
            if self.state is None:
                raise ConfigurationError("StateKeeper is not configured for stateful ETL mode.")
            queue_query = f"Queue: {queues} and " if queues else ""
            if (last_state := self.state.get(self.state_key)) is None:
                last_state = (
                    datetime.now() - timedelta(seconds=from_human_time(config.stateful_initial_range))
                ).strftime(config.datetime_query_format)
            updated_query = f'Updated: >= "{last_state}"'
            return f"{queue_query} {updated_query} {sort_by_updated_asc}".strip()

        def build_query_from_filters() -> str:
            queue_query = f"Queue: {queues}" if queues else ""
            from_ = datetime.now() - timedelta(seconds=from_human_time(search_range))
            updated_query = f'Updated: >= "{from_.strftime(config.datetime_query_format)}"' if search_range else ""
            and_ = " and" if all((queues, search_range)) else ""
            return f"{queue_query}{and_} {updated_query} {sort_by_updated_asc}".strip()

        params = {"query": None, "filter": {}, "order": default_order}
        if search_query:
            logger.info("Search query received, ignoring other filter params")
            params["query"] = append_sort_by(search_query, sort_by_updated_asc)
        elif stateful:
            params["query"] = build_stateful_query()
        elif queues or search_range:
            params["query"] = build_query_from_filters()
        else:
            raise ConfigurationError(
                "Pass one of param: search_query, queues, search_range. Or run ETL in stateful mode."
            )
        logger.debug(f"Builded search query: {params}")
        return params

    @monitoring.send_time_metric("issue_transform_time_seconds")
    def _transform(self, issue: Issues) -> ClickhousePayload:
        """Transform issue to storage-compatible payload format."""
        _issue = TrackerIssue(issue)
        changelog = _issue._changelog_events
        metrics = _issue.metrics()

        return ClickhousePayload(
            issue=fix_null_dates(_issue.to_dict()),
            changelog=[c.model_dump() for c in changelog] if changelog else [],
            metrics=[m.to_dict() for m in metrics] if metrics else [],
        )

    @monitoring.send_time_metric("export_and_transform_time_seconds")
    def _export_and_transform(
        self,
        query: str | None = None,
        filter: dict | list | None = None,
        order: dict | list | None = None,
        limit: int = 100,
    ) -> Tuple[List[dict], List[dict], List[dict], str | None]:
        """Collects and transforms metrics for found tasks."""
        issues = []
        metrics = []
        changelog_events = []
        issues_without_metrics = 0
        logger.info("Searching, exporting and transform issues...")

        found_issues = self.tracker.search_issues(query=query, filter=filter, order=order, limit=limit)
        if len(found_issues) == 0:
            logger.info("Nothing to export. Skipping ETL")
            return

        if isinstance(found_issues, SeekablePaginatedList):
            pagination = True
            logger.info("Paginated list received, possible new state will be calculated later")
        else:
            pagination = False
            possible_new_state = self._get_possible_new_state(TrackerIssue(found_issues[-1]))

        et_start_time = time.time()
        for i, tracker_issue in enumerate(found_issues):
            if config.log_etl_stats:
                if i == 0:
                    pass
                elif i % config.log_etl_stats_each_n_iter == 0:
                    elapsed_time = time.time() - et_start_time
                    log_etl_stats(iteration=i, remaining=len(found_issues), elapsed=elapsed_time)
            try:
                issue, changelog, issue_metrics = self._transform(tracker_issue).model_dump().values()
                if pagination and i == len(found_issues):
                    logger.info("Trying to get new state from last iteration")
                    possible_new_state = self._get_possible_new_state(TrackerIssue(tracker_issue))
                issues.append(issue)
                changelog_events.extend(changelog)
                if not issue_metrics:
                    logger.debug(f"Ignore {tracker_issue.key} because metrics is empty")
                    issues_without_metrics += 1
                else:
                    metrics.extend(issue_metrics)
                monitoring.send_count_metric("issues_total_processed_count", 1)
            except Forbidden as forbidden:
                logger.warning(f"Can't read {tracker_issue.key}, permission denied. Details: {forbidden}")
            except Exception as exc:
                logger.exception(f"Issue {tracker_issue.key} can't be transformed, details: {exc}")

        monitoring.send_gauge_metric("issues_without_metrics", value=issues_without_metrics)
        logger.info(
            f"Total issues: {len(issues)}, total metrics: {len(metrics)}, "
            f"total changelog events: {len(changelog_events)}, "
            f"ignored issues with empty metrics: {issues_without_metrics}"
        )
        return issues, changelog_events, metrics, possible_new_state

    @monitoring.send_time_metric("upload_to_storage_time_seconds")
    def _load_to_storage(self, database: str, table: str, payload: list, deduplicate: bool = True) -> dict:
        """Load transformed payload to storage."""
        logger.info(f"Inserting batch ({len(payload)}) to {database}.{table}...")
        self.clickhouse.insert_batch(database, table, payload)
        if deduplicate:
            logger.info(f"Optimizing {database}.{table} for deduplication...")
            self.clickhouse.deduplicate(database, table)

    @monitoring.send_time_metric("etl_duration_seconds")
    def run(
        self,
        *,
        stateful: bool = False,
        queues: str | None = None,
        search_query: str | None = None,
        search_range: str | None = None,
        limit: int = 100,
        ignore_exceptions: bool = True,
        auto_deduplicate: bool = True,
    ) -> None:
        """Runs main ETL process."""
        query = self._build_search_query(stateful, queues, search_query, search_range)
        try:
            issues, changelogs, metrics, possible_new_state = self._export_and_transform(**query, limit=limit)
            if stateful:
                logger.info(f"Possible new state: {possible_new_state}")
                last_saved_state = self.state.get(self.state_key)
                if last_saved_state == possible_new_state and len(issues) <= 1 and len(metrics) <= 1:
                    logger.info("Data already is up-to-date, skipping upload stage")
                    return
        except Exception as exc:
            logger.error(f"An error occured in ETL while exporting and transform: {exc}")
            if not ignore_exceptions:
                raise ExportOrTransformError(str(exc))

        if self.upload_to_storage and (issues or metrics or changelogs):
            try:
                if issues:
                    self._load_to_storage(self.database, self.issues_table, issues, deduplicate=auto_deduplicate)
                if metrics:
                    self._load_to_storage(self.database, self.metrics_table, metrics, deduplicate=auto_deduplicate)
                if changelogs:
                    self._load_to_storage(
                        self.database,
                        self.changelogs_table,
                        changelogs,
                        deduplicate=auto_deduplicate,
                    )
                success = True
            except Exception as exc:
                logger.error(f"An exception occured in ETL while uploading: {exc}")
                success = False
                if not ignore_exceptions:
                    raise UploadError(str(exc))
            else:
                if all((stateful, self.state, possible_new_state)):
                    self.state.set(self.state_key, possible_new_state)
                monitoring.send_gauge_metric("last_update_timestamp", value=int(time.time()))
            finally:
                monitoring.send_gauge_metric("etl_upload_status", value=1 if success else 2)
        else:
            print(issues)
            print(metrics)
            print(changelogs)
