CREATE TABLE IF NOT EXISTS `issues_changelog`
(
    `version` DateTime64(3, 'UTC') DEFAULT now(),
    `event_time` DateTime64(3, 'UTC') COMMENT 'Changelog event time',

    `issue_key` String COMMENT 'Issue key',
    `queue` LowCardinality(String) COMMENT 'Queue',
    `event_type` LowCardinality(String) COMMENT 'Event type',
    `transport` LowCardinality(String) COMMENT 'Event source, i.e. api, front, etc',
    `actor` String DEFAULT '' COMMENT 'Event initiator, i.e. employee name, robot name, etc',

    `changed_field` String COMMENT 'The field that was changed',
    `changed_from` String DEFAULT '' COMMENT 'Previous field value',
    `changed_to` String COMMENT 'New field value'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(event_time)
ORDER BY (issue_key, event_time, event_type, changed_field)
