import logging

from pydantic import BaseModel
from typing import List, Any
from tracker_exporter._typing import DateTimeISO8601Str, DateStr

from yandex_tracker_client.collections import Issues, IssueChangelog
from yandex_tracker_client.exceptions import NotFound

from tracker_exporter.models.base import Base
from tracker_exporter.models.base import (
    TrackerChangelogEvents,
    TrackerWorkflowTypes,
)
from tracker_exporter.utils.helpers import (
    calculate_time_spent,
    string_normalize,
    validate_resource,
    extract_changelog_field,
    convert_datetime,
    to_snake_case,
    to_human_time,
)
from tracker_exporter.config import config

logger = logging.getLogger(__name__)


class TrackerIssueChangelog(BaseModel):
    """This object represents a issue changelog events."""

    issue_key: str
    queue: str
    event_time: DateTimeISO8601Str
    event_type: str
    transport: str
    actor: str
    changed_field: Any
    changed_from: Any
    changed_to: Any


class TrackerIssueMetric(Base):
    """This object represents a issue metrics."""

    def __init__(
        self,
        issue_key: str,
        status_name: str,
        status_transitions_count: int,
        duration: int,
        busdays_duration: int,
        last_seen: str,
    ) -> None:
        self.issue_key = issue_key
        self.status_name = status_name
        self.status_transitions_count = status_transitions_count
        self.duration = duration
        self.human_readable_duration = to_human_time(self.duration)
        self.busdays_duration = busdays_duration
        self.human_readable_busdays_duration = to_human_time(self.busdays_duration)
        self.last_seen = last_seen


class TrackerIssue(Base):
    """This object represents a issue from Yandex.Tracker."""

    def __init__(self, issue: Issues) -> None:
        self._changelog_events: List[TrackerIssueChangelog] = []
        self._issue: Issues = issue
        self._metrics: dict = {}
        self._transform(self._issue)

    def _transform(self, issue: Issues) -> None:
        """Transformation of a issue into useful data."""
        logger.debug(f"Transforming issue {issue.key}...")

        self.queue: str = issue.queue.key
        self.issue_key: str = issue.key
        self.title: str = string_normalize(issue.summary)
        self.issue_type: str = to_snake_case(validate_resource(issue.type, "name"))
        self.priority: str = validate_resource(issue.priority, "name")
        self.assignee: str = validate_resource(issue.assignee, "email")
        self.author: str = validate_resource(issue.createdBy, "email")
        self.status: str = to_snake_case(validate_resource(issue.status, "name"))
        self.resolution: str = to_snake_case(validate_resource(issue.resolution, "name"))
        self.tags: list = issue.tags or []
        self.components: list = [c.name for c in issue.components if issue.components]
        self.is_resolved: bool = True if self.resolution is not None else False
        self.is_closed: bool = True if self.status in config.closed_issue_statuses or self.is_resolved else False
        self.created_at: DateTimeISO8601Str = convert_datetime(issue.createdAt)
        self.updated_at: DateTimeISO8601Str = convert_datetime(issue.updatedAt)
        self.resolved_at: DateTimeISO8601Str = convert_datetime(issue.resolvedAt)
        self.closed_at: DateTimeISO8601Str = self.resolved_at if self.is_resolved else None
        self.start_date: DateStr = validate_resource(issue, "start")
        self.end_date: DateStr = validate_resource(issue, "end")
        self.deadline: DateStr = validate_resource(issue, "deadline")
        self.story_points: int = validate_resource(issue, "storyPoints") or 0
        self.parent_issue_key: str = validate_resource(issue.parent, "key", low=False)
        self.epic_issue_key: str = validate_resource(issue.epic, "key", low=False)
        self.is_subtask: bool = True if any((self.parent_issue_key,)) else False
        self.qa_engineer: str = validate_resource(issue.qaEngineer, "email")
        self.aliases: list = validate_resource(issue, "aliases") or []
        self.was_moved: bool = False
        self.moved_at: DateTimeISO8601Str = None
        self.moved_by: str = None
        self._handle_strange_tracker_artifacts(self._issue)

    def _handle_strange_tracker_artifacts(self, issue: Issues):
        """
        Handling strange artifacts in the Yandex.Tracker.
        For some reason, the tracker can't find the project or sprint specified in the issue,
        like yandex_tracker_client.exceptions.NotFound: Sprint does not exist.
        """
        try:
            self.project = validate_resource(issue.project, "name")
        except NotFound as exc:
            logger.warning(f"Can't get info about specified project for issue {self.issue_key}. Details: {exc}")
            self.project = ""
        try:
            self.sprints: list = [s.name for s in issue.sprint if issue.sprint]
        except NotFound as exc:
            logger.warning(f"Can't get info about specified sprint for issue {self.issue_key}. Details: {exc}")
            self.sprints = []

    def _convert_and_save_changelog(self, event: IssueChangelog) -> None:
        """Convert issue changelog events to compatible format."""
        metadata = {
            "issue_key": event.issue.key,
            "queue": event.issue.queue.key,
            "event_time": convert_datetime(event.updatedAt),
            "event_type": event.type,
            "transport": event.transport,
            "actor": validate_resource(event.updatedBy, "email") or validate_resource(event.updatedBy, "name") or "",
        }

        for change in event.fields:
            try:  # Ah shit, here we go again
                changed_field = extract_changelog_field(change.get("field"))
                changed_from = extract_changelog_field(change.get("from"))
                changed_to = extract_changelog_field(change.get("to"))
            except NotFound as exc:
                logger.warning(
                    f"Tracker BUG, can't get info about '{changed_field}' in "
                    f"{self.issue_key}, the entity may have been deleted. Details: {exc}"
                )
                continue

            if changed_field is None or not any((changed_from, changed_to)):
                logger.debug(f"Skipping bad changelog event for {self.issue_key} ({changed_field}): {change}")
                continue

            self._changelog_events.append(
                TrackerIssueChangelog(
                    **metadata,
                    changed_field=changed_field,
                    changed_from=changed_from,
                    changed_to=changed_to,
                )
            )

    def _on_changelog_issue_moved(self, event: IssueChangelog) -> None:
        """Actions whe 'issue moved' event triggered."""
        logger.debug(f"Moved issue found: {self.issue_key}")
        self.was_moved = True
        self.moved_by = validate_resource(event.updatedBy, "email")
        self.moved_at = convert_datetime(event.updatedAt)

    def _on_changelog_issue_workflow(self, event: IssueChangelog) -> None:
        """Actions whe 'issue wofklow' event triggered."""
        logger.debug(f"Issue workflow fields found: {event.fields}")

        if len(event.fields) < 2:
            logger.debug(f"Not interesting event, skipping: {event.fields}")
            return

        # Keep only status transition events
        worklow_type = event.fields[0].get("field").id
        if worklow_type != TrackerWorkflowTypes.TRANSITION:
            logger.debug(f"Skipping {event.fields[0].get('field').id} for {self.issue_key}")
            return

        # Find datetimes between transition from status A to status B
        status = to_snake_case(event.fields[0].get("from").name.lower())
        event_start_time = event.fields[1].get("from") or self._issue.createdAt  # transition from the initial status
        event_end_time = event.fields[1].get("to")

        if event_start_time is None or event_end_time is None:
            logger.warning(
                f"Found corrupted changelog event with bad datetime range. "
                f"Perhaps this field is not a status. See details: "
                f"{self.issue_key}: {event.fields[1]}. All fields: {event.fields}"
            )
            return

        # Calculation of the time spent in the status
        start_time = convert_datetime(event_start_time)
        end_time = convert_datetime(event_end_time)
        total_status_time = calculate_time_spent(start_time, end_time)
        # TODO (akimrx): get workhours from queue settings?
        busdays_status_time = calculate_time_spent(start_time, end_time, busdays_only=True)

        # Custom logic for calculating the finish date of the issue,
        # because not everyone uses resolutions, sadly
        # Also, resolved tasks will be flagged as is_closed with closed_at the same as resoluition time
        transition_status = to_snake_case(event.fields[0].get("to").name.lower())
        if self.is_resolved and self.resolved_at:
            self.closed_at = self.resolved_at
        elif transition_status in config.closed_issue_statuses and self.status in config.closed_issue_statuses:
            self.closed_at = convert_datetime(event_end_time)

        try:
            self._metrics[status]["duration"] += total_status_time
            self._metrics[status]["busdays_duration"] += busdays_status_time
            self._metrics[status]["status_transitions_count"] += 1
        except (KeyError, AttributeError):
            self._metrics[status] = {
                "issue_key": self.issue_key,
                "status_name": status,
                "status_transitions_count": 1,
                "duration": total_status_time,
                "busdays_duration": busdays_status_time,
                "last_seen": convert_datetime(event_end_time),
            }

    def metrics(self) -> List[TrackerIssueMetric]:
        """
        All metrics are based on status change events in the task history.

        The metric of being in the status is considered
        only after the end of being in the calculated status.

        For example, the task has moved from the status "Open"
        to the status "In progress", in this case only the metric
        for "Open" will be considered.
        As soon as the status "In progress" is changed to any other,
        it will be calculated as a metric for "In progress".

        In other words, the current status of the task will not be
        calculated.
        """
        for event in self._issue.changelog:
            if config.changelog_export_enabled:
                self._convert_and_save_changelog(event)
            match event.type:
                case TrackerChangelogEvents.ISSUE_MOVED:
                    self._on_changelog_issue_moved(event)

                case TrackerChangelogEvents.ISSUE_WORKFLOW:
                    self._on_changelog_issue_workflow(event)

                case _:  # not interesting event
                    pass

        logger.debug(f"Metrics for {self.issue_key}: {self._metrics}")
        metrics = [TrackerIssueMetric(**metric) for _, metric in self._metrics.items()]

        return metrics
