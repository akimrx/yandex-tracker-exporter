# Yandex.Tracker Exporter

Export issue metadata & agile metrics to OLAP data storage. Metrics based on issue changelog.

## Self-hosted arch example

![](/docs/images/agile_metrics.png)

So, you can install Clickhouse with Clickhouse Proxy via Ansible role inside project.  
Edit the inventory file `ansible/inventory/hosts.yml` and just run ansible-playbook.

> **Attention:**
> For the role to work correctly, docker must be installed on the target server.

Example:
```bash

pip3 install -r requirements-dev.txt
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/clickhouse.yml --limit agile
```


## Serverless arch example

![](/docs/images/agile_metrics_cloud.png)

### Create a Managed Clickhouse cluster

> How to: https://cloud.yandex.com/en/docs/managed-clickhouse/operations/cluster-create

* Set user for exporter, example: `agile`
* Set a database name, example: `agile`
* Enable `Serverless access` flag
* For testing enable host public access
* Enable `Access from the management console` flag
* Run migration or manual create tables (see migration block [here](#migration), see [sql](/migrations/clickhouse/))

### Create Cloud Function

> How to: https://cloud.yandex.com/en/docs/functions/quickstart/create-function/python-function-quickstart

* Use Python >= 3.7
* Copy/paste example content from `examples/serverless` ([code](/examples/serverless/))
* Set entrypoint: `main.handler` (for code from examples)
* Set function timeout to `600`, because the launch can be long if there are a lot of updated issues during the collection period
* Set memory to `512MB` or more
* Add environment variables (see variables block [here](#environment-variables-settings))
    ```bash
    EXPORTER_TRACKER_TOKEN=XXXXXXXXXXXXXXXX
    EXPORTER_TRACKER_ORG_ID=123456
    EXPORTER_CLICKHOUSE_PROTO=https
    EXPORTER_CLICKHOUSE_CERT=/etc/ssl/certs/ca-certificates.crt
    EXPORTER_CLICKHOUSE_HTTP_PORT=8443
    EXPORTER_CLICKHOUSE_HOST=rc1b-xxxxxx.mdb.yandexcloud.net
    EXPORTER_CLICKHOUSE_DATABASE=agile
    EXPORTER_CLICKHOUSE_USER=agile
    EXPORTER_CLICKHOUSE_PASSWORD=xxxx
    EXPORTER_ENABLE_UPLOAD=true
    EXPORTER_ISSUES_SEARCH_INTERVAL=2h
* Release function
* Run test
* See logs

![](/docs/images/logs.png)


##### Serverless database connection without public access
If you don't want to enable clickhouse public access, use service account with such permissions - `serverless.mdbProxies.user` and set environment variables below:
```bash
EXPORTER_CLICKHOUSE_HOST=akfd3bhqk3xxxxxxxxxxx.clickhouse-proxy.serverless.yandexcloud.net
EXPORTER_CLICKHOUSE_SERVERLESS_PROXY_ID=akfd3bhqk3xxxxxxxxxxxxx
```

> How to create database connection: https://cloud.yandex.com/en/docs/functions/operations/database-connection

Also, the `EXPORTER_CLICKHOUSE_PASSWORD` variable with service account must be replaced by IAM-token. Keep this in mind. 
Probably, you should get it in the function code, because the IAM-token works for a limited period of time.

### Create Trigger

> How to: https://cloud.yandex.com/en/docs/functions/quickstart/create-trigger/timer-quickstart

* Create new trigger
* Choose type `Timer`
* Set interval every hour: `0 * ? * * *`
* Select your function
* Create serverless service account or use an existing one
* Save trigger


# Visualization

You can use any BI tool for visualization, for example:
- Yandex DataLens
- Apache Superset
- PowerBI
- Grafana

![](/docs/images/datalens_example.png)


# Migration

Based on [go-migrate](https://github.com/golang-migrate/migrate) tool.

## Download and install go-migrate tool

### macOS
```shell
wget https://github.com/golang-migrate/migrate/releases/download/v4.15.2/migrate.darwin-amd64.tar.gz -O migrate.tar.gz

tar xvf migrate.tar.gz
mv migrate ~/bin
```

### Linux
```shell
wget https://github.com/golang-migrate/migrate/releases/download/v4.15.2/migrate.linux-amd64.tar.gz -O migrate.tar.gz

tar -xvf migrate.tar.gz
mv migrate /usr/local/bin
```

## Run migration

Example bash script

```bash
#!/usr/bin/env bash

set -Eeuo pipefail

CLICKHOUSE_HOST="localhost"
CLICKHOUSE_TCP_PORT=9000
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_USER="default"
CLICKHOUSE_PASSWORD="strongpassword"

MIGRATION_SOURCE_PATH="file://${PWD}/../migrations/clickhouse"
MIGRATION_HISTORY_TABLE="ci_gomigrate_migrations"
MIGRATION_DATABASE="agile"

MIGRATION_CLICKHOUSE_DSN="clickhouse://${CLICKHOUSE_HOST}:${CLICKHOUSE_TCP_PORT}?username=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASSWORD}&database=${MIGRATION_DATABASE}&x-multi-statement=true&x-migrations-table=${MIGRATION_HISTORY_TABLE}"

prepare_migration() {
    echo "CREATE DATABASE IF NOT EXISTS ${MIGRATION_DATABASE}" | \
        curl "http://${CLICKHOUSE_HOST}:${CLICKHOUSE_HTTP_PORT}/?user=${CLICKHOUSE_USER}&password=${CLICKHOUSE_PASSWORD}" --data-binary @-

}

run_migration() {
    migrate -verbose \
        -source $MIGRATION_SOURCE_PATH \
        -database $MIGRATION_CLICKHOUSE_DSN \
        up

}

prepare_migration
run_migration
```

# Environment variables (settings)

| variable | require? | default | description |
|----------|----------|---------|-------------|
| `EXPORTER_LOGLEVEL` | ❌ | `info` | One of: `debug`, `info`, `warning`, `error`, `exception` |
| `EXPORTER_ENABLE_UPLOAD` | ❌ | `false` | Enable/disable upload to Clickhouse storage |
| `EXPORTER_MONITORING_ENABLED` | ❌ | `false` | Enable send statsd metrics |
| `EXPORTER_MONITORING_HOST` | ❌ | `localhost` | Monitoring statsd hostname |
| `EXPORTER_MONITORING_PORT` | ❌ | `8125` | Monitoring statsd UDP port |
| `EXPORTER_MONITORING_PREFIX` | ❌ | `tracker_exporter` | Prefix for all sent metrics, i.e.: `{prefix}_{metric_name}` |
| `EXPORTER_SENTRY_ENABLED` | ❌ | `false` | Send exceptions and errors to Sentry |
| `EXPORTER_SENTRY_DSN` | ❌ | None | Sentry DSN like https://{id}@{sentry_url} |
| `EXPORTER_TRACKER_TOKEN` | ✅ | None | Yandex.Tracker OAuth token |
| `EXPORTER_TRACKER_ORG_ID` | ✅ | None | Yandex.Tracker organization ID for Yandex.Tracker |
| `EXPORTER_TRACKER_ISSUES_SEARCH_RANGE` | ❌ | `4h` | The query search range for recently updated issues, i.e: `Updated >= now() - {VARIABLE}` |
| `EXPORTER_TRACKER_ISSUES_SEARCH_QUERY` | ❌ | None | The query search string like `Queue: SRE and status: closed` |
| `EXPORTER_TRACKER_ISSUES_FETCH_INTERVAL` | ❌ | `120` | Exporter job run interval in minutes for issue and metrics |
| `EXPORTER_CLOSED_ISSUES_STATUSES` | ❌ | `closed,rejected,released,resolved,cancelled` | Lowercase comma-separated status, which will be flagged as `is_closed` |
| `EXPORTER_CLICKHOUSE_PROTO` | ❌ | `http` | Clickhouse protocol - HTTP or HTTPS |
| `EXPORTER_CLICKHOUSE_HOST` | ❌ | `localhost` | Clickhouse hostname |
| `EXPORTER_CLICKHOUSE_HTTP_PORT` | ❌ | `8123` | Clickhouse HTTP(S) port |
| `EXPORTER_CLICKHOUSE_USER` | ❌ | `default` | Clickhouse read-write username |
| `EXPORTER_CLICKHOUSE_PASSWORD` | ✅ | None | Clickhouse user password. **If your clickhouse/user can work without password just ignore this variable.** |
| `EXPORTER_CLICKHOUSE_CACERT_PATH` | ❌ | `None` | Path to CA certificate. Only for HTTPS |
| `EXPORTER_CLICKHOUSE_SERVERLESS_PROXY_ID` | ❌ | `None` | Database connection ID. Only for serverless |
| `EXPORTER_CLICKHOUSE_DATABASE` | ❌ | `agile` | Database for exporter CH tables |
| `EXPORTER_CLICKHOUSE_ISSUES_TABLE` | ❌ | `issues` | Table when store issues metadata |
| `EXPORTER_CLICKHOUSE_ISSUE_METRICS_TABLE` | ❌ | `issue_metrics` | Table when store issue metrics |


# Usage

## Native

### Install from source

```bash

python3 -m venv venv
source venv/bin/activate
python3 setup.py install

export EXPORTER_TRACKER_TOKEN="xxxx"
export EXPORTER_TRACKER_ORG_ID="123456"

export EXPORTER_TRACKER_ISSUES_SEARCH_RANGE="6h"
export EXPORTER_TRACKER_FETCH_INTERVAL=30

export EXPORTER_CLICKHOUSE_USER="default"
export EXPORTER_CLICKHOUSE_PASSWORD="strongpassword"
export EXPORTER_CLICKHOUSE_HOST="clickhouse01.example.com"
export EXPORTER_CLICKHOUSE_HTTP_PORT="8121"

export EXPORTER_LOGLEVEL="info"
export EXPORTER_ENABLE_UPLOAD=true

tracker-exporter
```

### Install from pypi

```bash
pip3 install tracker-exporter
tracker-exporter
```

### Use .env file

```bash
tracker-exporter --env-file /home/akimrx/tracker/.settings
```


## Docker

```bash

cd yandex-tracker-exporter
touch .env  # prepare the environment variables file (dotenv), like the example above
docker-compose up -d --build
docker logs tracker-exporter -f
```

# Monitoring

| Metric name | Metric type | Labels | Description |
|-------------|-------------|--------|-------------|
| `tracker_exporter_clickhouse_insert_time_seconds` | `time` | `project` | Insert query time |
| `tracker_exporter_clickhouse_optimize_time_seconds` | `time` | `project` | Optimize query time |
| `tracker_exporter_clickhouse_inserted_rows` | `gauge` | `project`, `database`, `table` | Inserted rows to Clickhouse from last update |
| `tracker_exporter_cycle_time_total_processing_time_seconds` | `time` | `project` | Total issues processing time |
| `tracker_exporter_issue_transform_time_seconds` | `time` | `project` | Time of transformation of one issue into an object |
| `tracker_exporter_issues_search_time_seconds` | `time` | `project` | Yandex.Tracker search time |
| `tracker_exporter_issues_processing_time_seconds` | `time` | `project` | Time of transformation of batch issues into objects |
| `tracker_exporter_issues_total_processed_count` | `count` | `project`, `source` | Processed issues from Yandex.Tracker |
| `tracker_exporter_issues_without_metrics` | `gauge` | `project` | Issues with empty metrics |
| `tracker_exporter_upload_status` | `gauge` | `project` | Status of data upload to storage |
| `tracker_exporter_last_update_timestamp` | `timestamp gauge` | `project` | Timestamp of the last data upload to the storage |