#!/usr/bin/env python3

import os
import sys
import time
import signal
import logging
import warnings
import argparse

from datetime import datetime, timedelta
from dotenv import load_dotenv

import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler

parser = argparse.ArgumentParser("tracker-exporter")
parser.add_argument(
    "-e", "--env-file",
    metavar="file",
    dest="env_file",
    type=str,
    required=False,
    help="Path to .env file"
)
args = parser.parse_args()
load_dotenv(args.env_file)
warnings.filterwarnings("ignore")

# pylint: disable=C0413
from .errors import ExportError
from .services.monitoring import DogStatsdClient, sentry_events_filter
from .exporter import Exporter
from .__version__ import appname, version
from .defaults import (
    EXCLUDE_QUEUES,
    LOGLEVEL,
    UPLOAD_TO_STORAGE,
    TRACKER_ISSUES_UPDATE_INTERVAL,
    SENTRY_ENABLED,
    SENTRY_DSN,
)

logging.basicConfig(
    level=LOGLEVEL.upper(),
    datefmt="%Y-%m-%d %H:%M:%S",
    format="%(asctime)s [%(levelname)s] [%(name)s.%(funcName)s] %(message)s"
)
logging.getLogger("yandex_tracker_client").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
monitoring = DogStatsdClient()
exporter = Exporter()
logger.debug(f"Environment: {os.environ.items()}")


def signal_handler(sig, frame) -> None:  # pylint: disable=W0613
    if sig == signal.SIGINT:
        logger.warning("Received SIGINT, graceful shutdown...")
        scheduler.shutdown()
        sys.exit(0)


def configure_sentry() -> None:
    if SENTRY_ENABLED:
        assert SENTRY_DSN is not None
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=1.0,
            release=f"{appname}@{version}",
            before_send=sentry_events_filter
        )
    logger.info(f"Sentry send traces is {'enabled' if SENTRY_ENABLED else 'disabled'}")


def export_cycle_time(exclude_queues: str = EXCLUDE_QUEUES,
                      upload: bool = UPLOAD_TO_STORAGE,
                      ignore_exceptions: bool = True) -> None:
    try:
        inserted_rows = exporter.cycle_time(exclude_queues=exclude_queues, upload=upload)
        if inserted_rows > 0:
            monitoring.send_gauge_metric("last_update_timestamp", value=int(time.time()))
            monitoring.send_gauge_metric("upload_status", value=1)
    except Exception as exc:
        monitoring.send_gauge_metric("upload_status", value=2)
        logger.exception(f"Something error occured: {exc}")
        if not ignore_exceptions:
            raise ExportError(exc) from exc


def main() -> None:
    configure_sentry()
    signal.signal(signal.SIGINT, signal_handler)
    scheduler.start()
    scheduler.add_job(
        export_cycle_time,
        trigger="interval",
        name="issues_cycle_time_exporter",
        minutes=int(TRACKER_ISSUES_UPDATE_INTERVAL),
        max_instances=1,
        next_run_time=datetime.now() + timedelta(seconds=5)
    )
    signal.pause()


if __name__ == "__main__":
    main()
