#!/usr/bin/env bash

set -Eeuo pipefail

SYSTEM=$(uname -s)
ARCH=$(uname -p)

CLICKHOUSE_HOST=localhost
CLICKHOUSE_TCP_PORT=9000
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_USER=default

GO_MIGRATE_VERSION="v4.16.2"
MIGRATION_SOURCE_PATH="file://${PWD}/migrations/clickhouse"
MIGRATION_HISTORY_TABLE="ci_gomigrate_migrations"
MIGRATION_DATABASE="agile"

MIGRATION_CLICKHOUSE_DSN="clickhouse://${CLICKHOUSE_HOST}:${CLICKHOUSE_TCP_PORT}?username=${CLICKHOUSE_USER}&database=${MIGRATION_DATABASE}&x-multi-statement=true&x-migrations-table=${MIGRATION_HISTORY_TABLE}"

install_go_migrate() {
    echo "System is ${SYSTEM} (${ARCH})"
    if command -v ./migrate >/dev/null 2>&1; then
        echo "Tool for migration already installed, skipping installation"
    else
        echo "Installing go migrate tool..."
        if [ "${SYSTEM}" = "Darwin" ]; then
            if [ "${ARCH}" = "arm" ]; then
                wget https://github.com/golang-migrate/migrate/releases/download/${GO_MIGRATE_VERSION}/migrate.darwin-amd64.tar.gz -O migrate.tar.gz
            else
                wget https://github.com/golang-migrate/migrate/releases/download/${GO_MIGRATE_VERSION}/migrate.darwin-arm64.tar.gz -O migrate.tar.gz
            fi
            tar xvf migrate.tar.gz migrate
        elif [ "${SYSTEM}" = "Linux" ]; then
            wget https://github.com/golang-migrate/migrate/releases/download/${GO_MIGRATE_VERSION}/migrate.linux-amd64.tar.gz -O migrate.tar.gz
            tar -xvf migrate.tar.gz migrate
        fi
        chmod +x migrate
        rm ./migrate.tar.gz
    fi
}


prepare_database() {
    echo "CREATE DATABASE IF NOT EXISTS ${MIGRATION_DATABASE}" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-

}


prepare_migration() {
    echo "CREATE DATABASE IF NOT EXISTS ${MIGRATION_HISTORY_TABLE}" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-

}


run_migration() {
    ./migrate -verbose \
        -source $MIGRATION_SOURCE_PATH \
        -database $MIGRATION_CLICKHOUSE_DSN \
        up

}

recreate_views() {
    echo "DROP VIEW IF EXISTS ${MIGRATION_DATABASE}.issues_view" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-
    echo "DROP VIEW IF EXISTS ${MIGRATION_DATABASE}.issue_metrics_view" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-
    echo "DROP VIEW IF EXISTS ${MIGRATION_DATABASE}.issues_changelog_view" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-


    echo "CREATE VIEW IF NOT EXISTS ${MIGRATION_DATABASE}.issues_view AS SELECT * FROM ${MIGRATION_DATABASE}.issues FINAL" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-
    echo "CREATE VIEW IF NOT EXISTS ${MIGRATION_DATABASE}.issue_metrics_view AS SELECT * FROM ${MIGRATION_DATABASE}.issue_metrics FINAL" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-
    echo "CREATE VIEW IF NOT EXISTS ${MIGRATION_DATABASE}.issues_changelog_view AS SELECT * FROM ${MIGRATION_DATABASE}.issues_changelog FINAL" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}" --data-binary @-

}


install_go_migrate
prepare_database
prepare_migration
run_migration
recreate_views