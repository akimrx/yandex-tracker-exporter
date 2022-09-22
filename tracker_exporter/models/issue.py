import logging

from tracker_exporter.models.base import Base
from tracker_exporter.models.enums import (
    TrackerChangelogEvents,
    TrackerWorkflowTypes,
)
from tracker_exporter.services.monitoring import DogStatsdClient
from tracker_exporter.utils.helpers import (
    calculate_time_spent,
    string_normalize,
    validate_resource,
    to_simple_datetime,
    to_snake_case,
    to_human_time,
)
from tracker_exporter.defaults import CLOSED_ISSUE_STATUSES

logger = logging.getLogger(__name__)
monitoring = DogStatsdClient()


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

    def __init__(self, issue: object) -> None:
        self._issue = issue
        self._transform(self._issue)

    def _transform(self, issue: object) -> None:
        """Formation of a task object based on its metadata."""
        self.queue = issue.queue.key
        self.issue_key = issue.key
        self.title = string_normalize(issue.summary)
        self.issue_type = to_snake_case(validate_resource(issue.type, "name"))
        self.priority = validate_resource(issue.priority, "name")
        self.assignee = validate_resource(issue.assignee, "email")
        self.author = validate_resource(issue.createdBy, "email")
        self.status = to_snake_case(validate_resource(issue.status, "name"))
        self.resolution = to_snake_case(validate_resource(issue.resolution, "name"))
        self.tags = issue.tags or []
        self.components = [c.name for c in issue.components if issue.components]
        self.created_at = to_simple_datetime(issue.createdAt, date_only=True)
        self.updated_at = to_simple_datetime(issue.updatedAt, date_only=True)
        self.deadline = validate_resource(issue, "deadline")
        self.resolved_at = to_simple_datetime(issue.resolvedAt, date_only=True)
        self.start_date = validate_resource(issue, "start")
        self.end_date = validate_resource(issue, "end")
        self.story_points = validate_resource(issue, "storyPoints") or 0
        self.sprints = [s.name for s in issue.sprint if issue.sprint]
        self.parent_issue_key = validate_resource(issue.parent, "key", low=False)
        self.epic_issue_key = validate_resource(issue.epic, "key", low=False)
        self.is_subtask = True if any((self.parent_issue_key,)) else False
        self.is_closed = True if self.status in CLOSED_ISSUE_STATUSES else False
        self.is_resolved = True if self.resolution is not None else False
        self.qa_engineer = validate_resource(issue.qaEngineer, "email")

    @monitoring.send_count_metric("issues_total_processed_count", 1, tags=["source:issues"])
    def metrics(self) -> list:
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
        metrics_storage = {}

        for event in self._issue.changelog:
            if event.type == TrackerChangelogEvents.ISSUE_WORKFLOW:
                logger.debug(f"Issue workflow fields found: {event.fields}")
                worklow_type = event.fields[0].get("field").id
                # Keep only status transition events, drop otherwise
                if worklow_type != TrackerWorkflowTypes.TRANSITION:
                    logger.debug(f"Skipping {event.fields[0].get('field').id} for {self.issue_key}")
                    continue

                status = to_snake_case(event.fields[0].get("from").name.lower())
                event_start_time  = event.fields[1].get("from")
                event_end_time = event.fields[1].get("to")

                # Custom logic for calculating the completion date of the task,
                # because not everyone uses resolutions, sadly
                transition_status = to_snake_case(event.fields[0].get("to").name.lower())
                if transition_status in CLOSED_ISSUE_STATUSES and self.status in CLOSED_ISSUE_STATUSES:
                    self.closed_at = to_simple_datetime(event_end_time, date_only=True)  # pylint: disable=W0201

                if event_start_time is None or event_end_time is None:
                    continue

                # Calculation of the time spent in the status
                start_time = to_simple_datetime(event_start_time)
                end_time = to_simple_datetime(event_end_time)
                total_status_time = calculate_time_spent(start_time, end_time)
                busdays_status_time = calculate_time_spent(start_time, end_time, busdays_only=True)
                try:
                    metrics_storage[status]["duration"] += total_status_time
                    metrics_storage[status]["busdays_duration"] += busdays_status_time
                    metrics_storage[status]["status_transitions_count"] += 1
                except (KeyError, AttributeError):
                    metrics_storage[status] = dict(
                        issue_key=self.issue_key,
                        status_name=status,
                        status_transitions_count=1,
                        duration=total_status_time,
                        busdays_duration=busdays_status_time,
                        last_seen=to_simple_datetime(event_end_time)
                    )

        logger.debug(f"Metrics for {self.issue_key}: {metrics_storage}")
        metrics = [TrackerIssueMetric(**metric) for _, metric in metrics_storage.items()]
        return metrics
