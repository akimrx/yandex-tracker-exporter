CREATE VIEW IF NOT EXISTS `issues_view` AS
SELECT *
FROM `issues`
FINAL;

CREATE VIEW IF NOT EXISTS `issue_metrics_view` AS
SELECT *
FROM `issue_metrics`
FINAL;

CREATE VIEW IF NOT EXISTS `issues_changelog_view` AS
SELECT *
FROM `issues_changelog`
FINAL;
