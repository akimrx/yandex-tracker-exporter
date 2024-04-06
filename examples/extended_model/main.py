from tracker_exporter.models.issue import TrackerIssue
from tracker_exporter.utils.helpers import to_snake_case, validate_resource
from tracker_exporter import configure_sentry, run_etl

from yandex_tracker_client.collections import Issues


class CustomIssueFieldsMixin:
    """
    Additional custom fields for Yandex Tracker issue.
    Must be created in the Clickhouse issue table.
    """

    def __init__(self, issue: Issues) -> None:
        self.foo_custom_field = to_snake_case(validate_resource(issue, "fooCustomField"))
        self.bar_custom_field = validate_resource(issue, "barCustomField")
        self.baz = True if "baz" in issue.tags else False


class ExtendedTrackerIssue(CustomIssueFieldsMixin, TrackerIssue):
    """Extended Yandex Tracker issue model with custom fields."""

    def __init__(self, issue: Issues) -> None:
        super().__init__(issue)


def main() -> None:
    """Entry point."""
    run_etl(ignore_exceptions=False, issue_model=ExtendedTrackerIssue)


if __name__ == "__main__":
    configure_sentry()
    main()
