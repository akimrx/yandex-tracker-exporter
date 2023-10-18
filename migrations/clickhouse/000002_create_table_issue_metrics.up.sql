CREATE TABLE IF NOT EXISTS `issue_metrics`
(
    `version` DateTime64(3, 'UTC') DEFAULT now(),
    `last_seen` DateTime64(3, 'UTC') COMMENT 'The date when the issue was last in this status',

    `issue_key` String COMMENT 'Issue key',
    `status_name` LowCardinality(String) COMMENT 'Status name',
    `status_transitions_count` UInt8 COMMENT 'The number of transitions to this status',

    `duration` UInt32 COMMENT 'Time spent in the status in seconds (for all time)',
    `human_readable_duration` String DEFAULT '' COMMENT 'Human - readable format for duration',
    `busdays_duration` UInt32 COMMENT 'Time spent in the status in seconds (busdays only)',
    `human_readable_busdays_duration` String DEFAULT '' COMMENT 'Human - readable format for busdays_duration'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(last_seen)
ORDER BY (issue_key, status_name, last_seen)
