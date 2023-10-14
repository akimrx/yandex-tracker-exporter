import logging

from typing import List
from tracker_exporter._typing import DateTimeISO8601Str, DateStr

from yandex_tracker_client.collections import Issues

from tracker_exporter.models.base import Base
from tracker_exporter.models.base import (
    TrackerChangelogEvents,
    TrackerWorkflowTypes,
)
from tracker_exporter.utils.helpers import (
    calculate_time_spent,
    string_normalize,
    validate_resource,
    convert_datetime,
    to_snake_case,
    to_human_time,
)
from tracker_exporter.config import config

logger = logging.getLogger(__name__)


class TrackerIssueMetric(Base):
    """This object represents a issue metrics for TrackerIssue object."""
    def __init__(self,
                 issue_key: str,
                 status_name: str,
                 status_transitions_count: int,
                 duration: int,
                 busdays_duration: int,
                 last_seen: str):

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
        self._issue = issue
        self._metrics = {}
        self._transform(self._issue)

    def _transform(self, issue: Issues) -> None:
        """Formation of a task object based on its metadata."""
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
        self.project = validate_resource(issue.project, "name")
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
        self.sprints: list = [s.name for s in issue.sprint if issue.sprint]
        self.parent_issue_key: str = validate_resource(issue.parent, "key", low=False)
        self.epic_issue_key: str = validate_resource(issue.epic, "key", low=False)
        self.is_subtask: bool = True if any((self.parent_issue_key,)) else False
        self.qa_engineer: str = validate_resource(issue.qaEngineer, "email")
        self.aliases: list = validate_resource(issue, "aliases") or []
        self.was_moved: bool = False
        self.moved_at: DateTimeISO8601Str = None
        self.moved_by: str = None

    def _on_changelog_issue_moved(self, event: object) -> None:
        logger.debug(f"Moved issue found: {self.issue_key}")
        self.was_moved = True
        self.moved_by = validate_resource(event.updatedBy, "email")
        self.moved_at = convert_datetime(event.updatedAt)

    def _on_changelog_issue_workflow(self, event: object) -> None:
        logger.debug(f"Issue workflow fields found: {event.fields}")

        if len(event.fields) < 2:
            logger.debug(f"Not interesting event, skipping: {event.fields}")
            return

        status = to_snake_case(event.fields[0].get("from").name.lower())
        worklow_type = event.fields[0].get("field").id

        # Keep only status transition events
        if worklow_type != TrackerWorkflowTypes.TRANSITION:
            logger.debug(f"Skipping {event.fields[0].get('field').id} for {self.issue_key}")
            return

        event_start_time  = event.fields[1].get("from")
        event_end_time = event.fields[1].get("to")
        if event_start_time is None or event_end_time is None:
            logger.warning(
                f"Found corrupted changelog event with bad datetime range: "
                f"{self.issue_key}: {event.fields[1]}"
            )
            return

        # Custom logic for calculating the completion date of the task,
        # because not everyone uses resolutions, sadly
        # Also, resolved tasks will be flagged as is_closed with closed_at the same as resoluition time
        transition_status = to_snake_case(event.fields[0].get("to").name.lower())
        if self.is_resolved and self.resolved_at:
            self.closed_at = self.resolved_at
        elif (
            transition_status in config.closed_issue_statuses
            and self.status in config.closed_issue_statuses
        ):
            self.closed_at = convert_datetime(event_end_time)

        # Calculation of the time spent in the status
        start_time = convert_datetime(event_start_time)
        end_time = convert_datetime(event_end_time)
        total_status_time = calculate_time_spent(start_time, end_time)
        # TODO (akimrx): get workhours from queue settings?
        busdays_status_time = calculate_time_spent(start_time, end_time, busdays_only=True)

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
                "last_seen": convert_datetime(event_end_time)
            }

    def metrics(self) -> List[TrackerIssueMetric]:
        """
        All metrics are based on status change events in the task history.
        The method has the ability to filter only the necessary statuses
        passed in the argument.

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
