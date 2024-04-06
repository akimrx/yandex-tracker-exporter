#!/usr/bin/env python3

import os
import sys
import signal
import logging
import warnings
import argparse

from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv

import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler

parser = argparse.ArgumentParser("tracker-exporter")
parser.add_argument(
    "-e",
    "--env-file",
    metavar="file",
    dest="env_file",
    type=str,
    required=False,
    help="Path to .env file",
)
parser.add_argument("--run-once", dest="run_once", action="store_true", help="Run ETL once.")
args, _ = parser.parse_known_args()
warnings.filterwarnings("ignore")

if args.env_file:
    load_dotenv(args.env_file)
else:
    load_dotenv(find_dotenv())

# pylint: disable=C0413
from tracker_exporter.services.monitoring import sentry_events_filter
from tracker_exporter.state.managers import AbstractStateManager
from tracker_exporter.state.factory import StateManagerFactory, IObjectStorageProps
from tracker_exporter.models.issue import TrackerIssue
from tracker_exporter.etl import YandexTrackerETL
from tracker_exporter.services.tracker import YandexTrackerClient
from tracker_exporter.services.clickhouse import ClickhouseClient
from tracker_exporter._meta import appname, version
from tracker_exporter.config import config

logging.basicConfig(
    level=config.loglevel.upper(),
    datefmt="%Y-%m-%d %H:%M:%S",
    format="%(asctime)s.%(msecs)03d [%(levelname)s] [%(name)s.%(funcName)s] %(message)s",
)
logging.getLogger("yandex_tracker_client").setLevel(config.tracker.loglevel.upper())
logger = logging.getLogger(__name__)
logger.debug(f"Environment: {os.environ.items()}")
logger.debug(f"Configuration dump: {config.model_dump()}")

scheduler = BackgroundScheduler()


def signal_handler(sig, frame) -> None:  # pylint: disable=W0613
    """Graceful shutdown."""
    if sig in (
        signal.SIGINT,
        signal.SIGTERM,
    ):
        logger.warning(f"Received {signal.Signals(sig).name}, graceful shutdown...")
        scheduler.shutdown()
        sys.exit(0)


def configure_sentry() -> None:
    """Configure Sentry client for send exception stacktraces."""
    if config.monitoring.sentry_enabled:
        assert config.monitoring.sentry_dsn is not None
        sentry_sdk.init(
            dsn=config.monitoring.sentry_dsn,
            traces_sample_rate=1.0,
            release=f"{appname}@{version}",
            before_send=sentry_events_filter,
        )
    logger.info(f"Sentry send traces is {'enabled' if config.monitoring.sentry_enabled else 'disabled'}")


def configure_state_manager() -> AbstractStateManager | None:
    """Configure StateKeeper for ETL stateful mode."""
    if not config.stateful:
        return

    match config.state.storage:
        case "jsonfile":
            s3_props: IObjectStorageProps = IObjectStorageProps(
                bucket_name=config.state.jsonfile_s3_bucket,
                access_key_id=config.state.jsonfile_s3_access_key,
                secret_key=config.state.jsonfile_s3_secret_key,
                endpoint_url=config.state.jsonfile_s3_endpoint,
                region=config.state.jsonfile_s3_region,
            )
            return StateManagerFactory.create_file_state_manager(
                strategy=config.state.jsonfile_strategy, filename=config.state.jsonfile_path, **s3_props
            )
        case "redis":
            return StateManagerFactory.create_redis_state_manager(config.state.redis_dsn)
        case "custom":
            raise NotImplementedError
        case _:
            raise ValueError


def run_etl(ignore_exceptions: bool = False, issue_model: TrackerIssue = TrackerIssue) -> None:
    """Start ETL process."""
    etl = YandexTrackerETL(
        tracker_client=YandexTrackerClient(),
        clickhouse_client=ClickhouseClient(),
        state_manager=configure_state_manager(),
        issue_model=issue_model,
    )
    etl.run(
        stateful=config.stateful,
        queues=config.tracker.search.queues,
        search_query=config.tracker.search.query,
        search_range=config.tracker.search.range,
        limit=config.tracker.search.per_page_limit,
        ignore_exceptions=ignore_exceptions,
        auto_deduplicate=config.clickhouse.auto_deduplicate,
    )


def main() -> None:
    """Entry point for CLI command."""
    configure_sentry()

    if args.run_once:
        logger.info("A one-time launch command is received, the scheduler setting will be skipped")
        run_etl()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    scheduler.start()
    scheduler.add_job(
        run_etl,
        trigger="interval",
        name="tracker_etl_default",
        minutes=int(config.etl_interval_minutes),
        max_instances=1,
        next_run_time=datetime.now() + timedelta(seconds=5),
    )
    signal.pause()


if __name__ == "__main__":
    main()
