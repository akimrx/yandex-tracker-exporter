[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tracker-exporter.svg)](https://pypi.org/project/tracker-exporter/)
[![PyPi Package](https://img.shields.io/pypi/v/tracker-exporter.svg)](https://pypi.org/project/tracker-exporter/)
[![Codecov](https://codecov.io/gh/akimrx/yandex-tracker-exporter/branch/master/graph/badge.svg)](https://app.codecov.io/gh/akimrx/yandex-tracker-exporter)
[![Tests](https://github.com/akimrx/yandex-tracker-exporter/workflows/Tests/badge.svg)](https://github.com/akimrx/yandex-tracker-exporter)
[![PyPI](https://github.com/akimrx/yandex-tracker-exporter/workflows/PyPI/badge.svg)](https://github.com/akimrx/yandex-tracker-exporter)
[![Docker](https://github.com/akimrx/yandex-tracker-exporter/workflows/Docker/badge.svg)](https://github.com/akimrx/yandex-tracker-exporter)


# Yandex.Tracker ETL

Export issue metadata & agile metrics, transform and load to OLAP data storage. Metrics based on issue changelog.  

⚠️ **Important**  
**Versions 1.x.x incompatible with 0.1.x. New versions works only on Python >= 3.10**

> You can fork this repository and refine the tool the way you want. Or use it as it is - this will allow you to build basic analytics on the tasks from Yandex.Tracker.

Require:
* Python `>=3.10.*`
* Clickhouse + specific [tables](/migrations/clickhouse/) (how to run [migration](#migration))

## What does this tool do?

**ETL** – Export, transform, load.

It's simple. It doesn't do anything supernatural, it doesn't have Rocket Science in it.  
This is a simple ant with some mathematical abilities that takes data from one place, sorts/transforms/adapts/calculate them and puts them in another place.  
Sometimes he has to go to a lot of endpoints to collect what needs to be taken to the storage (that's the way Yandex.Tracker API).


**Collects:**
- Issue metadata (i.e. title, author, assignee, components, tags, status, etc)
- Issue changelog (i.e the history of all the events that occurred with the task)
- Calculated issue metrics by status (i.e. the time spent in a particular status)

## Tech stats

> Metrics based on 100,000+ constantly changing production issues

- **CPU usage**: from `2%` to `10%`
- **Memory usage (RSS):** from `48MB` to `256MB`
- **Average processing time per issue (metrics + issue metadata)**: 1.5 seconds
- **Average processing time per issue (with full changelog export):** 7 seconds

### Why is it taking so long?

This is how the tracker API and the library I use work. To get additional information about the task, you need to make a subquery in the API. For example, get the status name, employee name, and so on. When collecting data about a single task, more than several dozen HTTP requests can be executed.

This is also the answer to the question why the tool is not asynchronous. Limits in the API would not allow effective use of concurrency.

The processing speed of one issue depends on how many changes there are in the issue in its history. More changes means longer processing.

## Usage

### Native

#### Install from source

```bash
# prepare virtual environment
python3 -m venv venv
source venv/bin/activate
make install

# configure environment variables
export EXPORTER_TRACKER__TOKEN=your_token
export EXPORTER_TRACKER__CLOUD_ORG_ID=your_org_id
export EXPORTER_CLICKHOUSE__HOST=localhost
export EXPORTER_CLICKHOUSE__PORT=8123
export EXPORTER_STATEFUL="true"
export EXPORTER_STATE__STORAGE=jsonfile
export EXPORTER_STATE__JSONFILE_STRATEGY=local
export EXPORTER_STATE__JSONFILE_PATH=./state.json

# run
tracker-exporter
```

#### Install from PyPI

```bash
pip3 install tracker-exporter
tracker-exporter
```

#### Configure via .env file

Read about the settings [here](#environment-variables-settings)

```bash
tracker-exporter --env-file /home/akimrx/tracker/.settings
```


### Docker

```bash

cd yandex-tracker-exporter/docker
docker-compose up -d
docker logs tracker-exporter -f
```

## On-premise arch example

![](/docs/images/agile_metrics.png)

### On-premise Clickhouse

So, you can install Clickhouse with Proxy via [Ansible role inside project (previous versions)](https://github.com/akimrx/yandex-tracker-exporter/tree/v0.1.19/ansible).  
Edit the inventory file `ansible/inventory/hosts.yml` and just run ansible-playbook.

> **Attention:**
> For the role to work correctly, docker must be installed on the target server.

Example Clickhouse installation:
```bash
git clone https://github.com/akimrx/yandex-tracker-exporter.git
cd yandex-tracker-exporter
git checkout v0.1.19
python3 -m venv venv && source venv/bin/activate
pip3 install -r requirements-dev.txt
cd ansible
ansible-playbook -i inventory/hosts.yml playbooks/clickhouse.yml --limit agile
```

Also, you can use [this extended Clickhouse role](https://github.com/akimrx/ansible-clickhouse-role)


## Yandex.Cloud – Cloud Functions

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

* Use Python >= 3.10
* Copy/paste example content from `examples/serverless` ([code](/examples/serverless/))
* Set entrypoint: `main.handler` (for code from examples)
* Set function timeout to `600`, because the launch can be long if there are a lot of updated issues during the collection period
* Set memory to `512MB` or more
* Add environment variables (see variables block [here](#configuration-via-environment-variables))
```ini
EXPORTER_TRACKER__TOKEN=XXXXXXXXXXXXXXXX
EXPORTER_TRACKER__CLOUD_ORG_ID=123456
EXPORTER_TRACKER__SEARCH__RANGE=2h
EXPORTER_ENABLE__UPLOAD="true"
EXPORTER_CLICKHOUSE__PROTO=https
EXPORTER_CLICKHOUSE__CACERT_PATH=/etc/ssl/certs/ca-certificates.crt
EXPORTER_CLICKHOUSE__PORT=8443
EXPORTER_CLICKHOUSE__HOST=rc1b-xxxxxx.mdb.yandexcloud.net
EXPORTER_CLICKHOUSE__USER=agile
EXPORTER_CLICKHOUSE__PASSWORD=xxxx
```

* Release function
* Run test
* See logs

![](/docs/images/logs.png)


##### Serverless database connection without public access
If you don't want to enable clickhouse public access, use service account with such permissions - `serverless.mdbProxies.user` and set environment variables below:

```bash
EXPORTER_CLICKHOUSE__HOST=akfd3bhqk3xxxxxxxxxxx.clickhouse-proxy.serverless.yandexcloud.net
EXPORTER_CLICKHOUSE__SERVERLESS_PROXY_ID=akfd3bhqk3xxxxxxxxxxxxx
```

> How to create database connection: https://cloud.yandex.com/en/docs/functions/operations/database-connection

Also, the `EXPORTER_CLICKHOUSE__PASSWORD` variable with service account must be replaced by IAM-token. Keep this in mind. 
Probably, you should get it in the function code, because the IAM-token works for a limited period of time.

### Create Trigger

> How to: https://cloud.yandex.com/en/docs/functions/quickstart/create-trigger/timer-quickstart

* Create new trigger
* Choose type `Timer`
* Set interval every hour: `0 * ? * * *`
* Select your function
* Create serverless service account or use an existing one
* Save trigger


## Yandex.Cloud – Serverless Containers

TODO


# Visualization

You can use any BI/observability tool for visualization, for example:
- Yandex DataLens (btw, this is [opensource](https://github.com/datalens-tech/datalens))
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

Example bash script below.  
See full example script [here](/data-migrate.sh)

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

# Configuration via environment variables

See config declaration [here](/tracker_exporter/config.py)

## General settings

| variable | description |
|----------|-------------|
| `EXPORTER_STATEFUL` | Enable stateful mode. Required `EXPORTER_STATE__*` params. Default is `False` |
| `EXPORTER_STATEFUL_INITIAL_RANGE` | Initial search range when unknown last state. Default: `1w` |
| `EXPORTER_CHANGELOG_EXPORT_ENABLED` | Enable export all issues changelog to Clickhouse. Can greatly slow down exports. Default is `True` |
| `EXPORTER_LOGLEVEL` | ETL log level. Default: `info` |
| `EXPORTER_LOG_ETL_STATS` | Enable logging transform stats every N iteration. Default is `True` |
| `EXPORTER_LOG_ETL_STATS_EACH_N_ITER` | How many iterations must pass to log stats. Default is `100` |
| `EXPORTER_WORKDAYS` | Workdays for calculate business time. 0 - mon, 6 - sun. Default: `[0,1,2,3,4]` |
| `EXPORTER_BUSINESS_HOURS_START` | Business hours start for calculate business time. Default: `09:00:00` |
| `EXPORTER_BUSINESS_HOURS_END` | Business hours end for calculate business time. Default: `22:00:00` |
| `EXPORTER_DATETIME_RESPONSE_FORMAT` | Yandex.Tracker datetime format in responses. Default: `%Y-%m-%dT%H:%M:%S.%f%z` |
| `EXPORTER_DATETIME_QUERY_FORMAT` | Datetime format for search queries. Default: `%Y-%m-%d %H:%M:%S` |
| `EXPORTER_DATETIME_CLICKHOUSE_FORMAT` | Datetime format for Clickhouse. Default: `%Y-%m-%dT%H:%M:%S.%f` |
| `EXPORTER_ETL_INTERVAL_MINUTES` | Interval between run ETL. Default: `30` (minutes) |
| `EXPORTER_CLOSED_ISSUE_STATUSES` | Statuses for mark issue as closed. Default: `closed,rejected,resolved,cancelled,released` |
| `EXPORTER_NOT_NULLABLE_FIELDS` | Fields that should never be null (e.g. dates). Default: all datetime fields |

## Tracker settings

| variable | description |
|----------|-------------|
| `EXPORTER_TRACKER__LOGLEVEL` | Log level for Yandex.Tracker SDK. Default: `warning` |
| `EXPORTER_TRACKER__TOKEN` | OAuth2 token. Required if `EXPORTER_TRACKER__IAM_TOKEN` is not passed |
| `EXPORTER_TRACKER__ORG_ID` | Yandex360 organization ID. Required if `EXPORTER_TRACKER__CLOUD_ORG_ID` is not passed |
| `EXPORTER_TRACKER__IAM_TOKEN` | Yandex.Cloud IAM token. Required if `EXPORTER_TRACKER__TOKEN` is not passed |
| `EXPORTER_TRACKER__CLOUD_ORG_ID` | Yandex.Cloud organization ID. Required if `EXPORTER_TRACKER__ORG_ID` is not passed |
| `EXPORTER_TRACKER__TIMEOUT` | Yandex.Tracker HTTP requests timeout. Default: `10` (sec) |
| `EXPORTER_TRACKER__MAX_RETRIES` | Yandex.Tracker HTTP requests max retries. Default: `10` |
| `EXPORTER_TRACKER__LANGUAGE` | Yandex.Tracker language. Default: `en` |
| `EXPORTER_TRACKER__TIMEZONE` | Yandex.Tracker timezone. Default: `Europe/Moscow` |
| `EXPORTER_TRACKER__SEARCH__QUERY` | Custom query for search issues. This variable has the highest priority and overrides other search parameters. Default is empty |
| `EXPORTER_TRACKER__SEARCH__RANGE` | Search issues window. Has no effect in stateful mode. Default: `2h` |
| `EXPORTER_TRACKER__SEARCH__QUEUES` | Include or exclude queues in search. Example: `DEV,SRE,!TEST,!TRASH` Default is empty |
| `EXPORTER_TRACKER__SEARCH__PER_PAGE_LIMIT` | Search results per page. Default: `100` |

## Clickhouse settings

| variable | description |
|----------|-------------|
| `EXPORTER_CLICKHOUSE__ENABLE_UPLOAD` | Enable upload data to Clickhouse. Default is `True` |
| `EXPORTER_CLICKHOUSE__HOST` | Clickhouse host. Default: `localhost` |
| `EXPORTER_CLICKHOUSE__PROTO` | Clickhouse protocol: http or https. Default: `http` |
| `EXPORTER_CLICKHOUSE__PORT` | Clickhouse HTTP(S) port. Default: `8123`
| `EXPORTER_CLICKHOUSE__CACERT_PATH` | Path to CA cert. Only for HTTPS proto. Default is empty |
| `EXPORTER_CLICKHOUSE__SERVERLESS_PROXY_ID` | Yandex Cloud Functions proxy ID. Default is empty |
| `EXPORTER_CLICKHOUSE__USERNAME` | Clickhouse username. Default: `default` |
| `EXPORTER_CLICKHOUSE__PASSWORD` | Clickhouse password. Can be empty. Default is empty |
| `EXPORTER_CLICKHOUSE__DATABASE` | Clickhouse database. Default: `agile` |
| `EXPORTER_CLICKHOUSE__ISSUES_TABLE` | Clickhouse table for issues metadata. Default: `issues` |
| `EXPORTER_CLICKHOUSE__ISSUE_METRICS_TABLE` | Clickhouse table for issue metrics. Default: `issue_metrics` |
| `EXPORTER_CLICKHOUSE__ISSUES_CHANGELOG_TABLE` | Clickhouse table for issues changelog. Default: `issues_changelog` |
| `EXPORTER_CLICKHOUSE__AUTO_DEDUPLICATE` | Execute `OPTIMIZE` after each `INSERT`. Default is `True` |
| `EXPORTER_CLICKHOUSE__BACKOFF_BASE_DELAY` | Base delay for backoff strategy. Default: `0.5` (sec) |
| `EXPORTER_CLICKHOUSE__BACKOFF_EXPO_FACTOR` | Exponential factor for multiply every try. Default: `2.5` (sec) |
| `EXPORTER_CLICKHOUSE__BACKOFF_MAX_TRIES` | Max tries for backoff strategy. Default: `3` |
| `EXPORTER_CLICKHOUSE__BACKOFF_JITTER` | Enable jitter (randomize delay) for retries. Default: `True` |

## State settings

| variable | description |
|----------|-------------|
| `EXPORTER_STATE__STORAGE` | Storage type for StateKeeper. Can be: `jsonfile`, `redis`, `custom`. Default: `jsonfile` |
| `EXPORTER_STATE__REDIS_DSN` | Connection string for Redis state storage when storage type is `redis`. Default is empty. |
| `EXPORTER_STATE__JSONFILE_STRATEGY` | File store strategy for `jsonfile` storage type. Can be `s3` or `local`. Default: `local` |
| `EXPORTER_STATE__JSONFILE_PATH` | Path to JSON state file. Default: `./state.json` |
| `EXPORTER_STATE__JSONFILE_S3_BUCKET` | Bucket for `s3` strategy. Default is empty |
| `EXPORTER_STATE__JSONFILE_S3_REGION` | Region for `s3` strategy. Default is `eu-east-1` |
| `EXPORTER_STATE__JSONFILE_S3_ENDPOINT` | Endpoint URL for `s3` strategy. Default is empty |
| `EXPORTER_STATE__JSONFILE_S3_ACCESS_KEY` | AWS access key id for `s3` strategy. Default is empty |
| `EXPORTER_STATE__JSONFILE_S3_SECRET_KEY` | AWS secret key for `s3` strategy. Default is empty |
| `EXPORTER_STATE__CUSTOM_STORAGE_PARAMS` | Settings for custom storage params as `dict`. Default: `{}` |

## Observability settings

| variable | description |
|----------|-------------|
| `EXPORTER_MONITORING__METRICS_ENABLED` | Enable send statsd tagged metrics. Default is `False` |
| `EXPORTER_MONITORING__METRICS_HOST` | DogStatsD / statsd host. Default: `localhost` |
| `EXPORTER_MONITORING__METRICS_PORT` | DogStatsD / statsd port. Default: `8125` |
| `EXPORTER_MONITORING__METRICS_BASE_PREFIX` | Prefix for metrics name. Default: `tracker_exporter` |
| `EXPORTER_MONITORING__METRICS_BASE_LABELS` | List of tags for metrics. Example: `["project:internal",]`. Default is empty |
| `EXPORTER_MONITORING__SENTRY_ENABLED` | Enable send exception stacktrace to Sentry. Default is `False` |
| `EXPORTER_MONITORING__SENTRY_DSN` | Sentry DSN. Default is empty |


# Monitoring

Based on DogStatsD tagged format. VictoriaMetrics compatible.

| Metric name | Metric type | Labels | Description |
|-------------|-------------|--------|-------------|
| `tracker_exporter_issue_transform_time_seconds` | time | - | Duration of transform per task (data packing to the model) |
| `tracker_exporter_issues_total_processed_count` | count | - | Total issues processed |
| `tracker_exporter_issues_search_time_seconds` | time | - | Yandex.Tracker search duration time in seconds |
| `tracker_exporter_issues_without_metrics` | count | - | Issues with empty metrics (no changelog) |
| `tracker_exporter_issue_prefetch_seconds` | time | - | Pre-transform data duration in seconds |
| `tracker_exporter_comments_fetch_seconds` | time | - | Comments fetch duration in seconds |
| `tracker_exporter_etl_duration_seconds` | time | - | ETL full pipeline duration in seconds |
| `tracker_exporter_etl_upload_status` | gauge | - | Last upload status, 1 - success, 2 - fail |
| `tracker_exporter_export_and_transform_time_seconds` | time | - | Overall export and transform duration in seconds |
| `tracker_exporter_upload_to_storage_time_seconds` | time | - | Overall insert duration time in seconds |
| `tracker_exporter_last_update_timestamp` | gauge | - | Last data update timestamp |
| `tracker_exporter_clickhouse_insert_time_seconds` | time | database, table | Insert per table duration time in seconds |
| `tracker_exporter_clickhouse_inserted_rows` | count | database, table | Inserted rows per table |
| `tracker_exporter_clickhouse_deduplicate_time_seconds` | time | database, table | Optimize execute time duration in seconds |