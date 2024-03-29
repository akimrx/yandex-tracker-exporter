CREATE TABLE IF NOT EXISTS `issues`
(
    `version` DateTime64(3, 'UTC') DEFAULT now() COMMENT 'Row version',

    `queue` LowCardinality(String) COMMENT 'Queue key',
    `title` String DEFAULT '' COMMENT 'Issue summary',
    `issue_key` String COMMENT 'Unique issue key like TEST-1',
    `issue_type` LowCardinality(String) COMMENT 'Issue type',
    `priority` LowCardinality(String) COMMENT 'Issue priority',
    `status` LowCardinality(String) COMMENT 'Last issue status',
    `resolution` LowCardinality(String) DEFAULT '' COMMENT 'Issue resolution',

    `assignee` String DEFAULT '' COMMENT 'Issue assignee',
    `author` String DEFAULT '' COMMENT 'Issue creator',
    `qa_engineer` String DEFAULT '' COMMENT 'QA engineer who conducted the testing',

    `tags` Array(String) COMMENT 'Issue labels',
    `components` Array(String) COMMENT 'Issue components',
    `project` LowCardinality(String) DEFAULT '' COMMENT 'Related project',

    `created_at` DateTime64(3, 'UTC') COMMENT 'Issue creation date',
    `updated_at` DateTime64(3, 'UTC') COMMENT 'Date of the last update of the issue',
    `deadline` Date DEFAULT 0 COMMENT 'Deadline for completing the issue',
    `closed_at` DateTime64(3, 'UTC') DEFAULT 0 COMMENT 'Closing date of the issue without resolution, based on custom closing statuses',
    `resolved_at` DateTime64(3, 'UTC') DEFAULT 0 COMMENT 'Closing date of the issue with the resolution',
    `start_date` Date DEFAULT 0 COMMENT 'Start date (fact, manual field, gantt)',
    `end_date` Date DEFAULT 0 COMMENT 'End date (fact, manual field, gantt)',

    `is_subtask` UInt8 DEFAULT 0 COMMENT 'Subtask flag',
    `is_closed` UInt8 DEFAULT 0 COMMENT 'Issue completion flag (based on custom closing statuses)',
    `is_resolved` UInt8 DEFAULT 0 COMMENT 'Issue completion flag (with resolution)',

    `story_points` Float32 DEFAULT 0.0 COMMENT 'Estimating the cost of the issue',
    `sprints` Array(String) COMMENT 'Sprints in which the issue participated',
    `parent_issue_key` String DEFAULT '' COMMENT 'The key of the parent issue, like TEST-1',
    `epic_issue_key` String DEFAULT '' COMMENT 'Epic key, like GOAL-1',

    `aliases` Array(String) COMMENT 'All previous issue keys',
    `was_moved` UInt8 DEFAULT 0 COMMENT 'Has the task been moved from another queue',
    `moved_at` DateTime64(3, 'UTC') DEFAULT 0 COMMENT 'The date the queue was changed if the task was moved',
    `moved_by` String DEFAULT '' COMMENT 'The employee who moved the task'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(updated_at)
ORDER BY issue_key
