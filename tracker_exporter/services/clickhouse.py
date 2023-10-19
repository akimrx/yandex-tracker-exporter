import json
import logging

from typing import List, Dict

import requests
from requests import Response, ConnectionError, Timeout

from tracker_exporter.exceptions import ClickhouseError
from tracker_exporter.utils.helpers import backoff
from tracker_exporter.models.base import ClickhouseProto
from tracker_exporter.config import config, monitoring

logger = logging.getLogger(__name__)


class ClickhouseClient:
    """This class provide simple facade interface for Clickhouse."""

    def __init__(
        self,
        host: str = config.clickhouse.host,
        port: int = config.clickhouse.port,
        username: str = config.clickhouse.username,
        password: str = config.clickhouse.password,
        proto: ClickhouseProto = config.clickhouse.proto,
        cacert: str = config.clickhouse.cacert_path,
        serverless_proxy_id: str = config.clickhouse.serverless_proxy_id,
        params: dict = {},
        http_timeout: int = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.proto = proto
        self.cacert = cacert
        self.serverless_proxy_id = serverless_proxy_id
        self.params = params
        self.timeout = int(http_timeout)
        self.headers = {}

        self._prepare_headers()
        if self.proto == ClickhouseProto.HTTPS:
            assert self.cacert is not None

    def _prepare_headers(self):
        # fmt: off
        self.headers = {
            "Content-Type": "application/json",
            "X-Clickhouse-User": self.username
        }  # fmt: on
        if self.password is not None:
            self.headers["X-Clickhouse-Key"] = self.password

    def _prepare_query_params(self):
        params = self.params.copy()

        if params.get("user") is not None:
            logger.warning("Removed 'user' key:value from params, please pass 'user' via arg")
            del params["user"]

        if params.get("password") is not None:
            logger.warning("Removed 'password' key:value from params, please pass 'password' via arg")
            del params["password"]

        if self.serverless_proxy_id:
            self.params["database"] = self.serverless_proxy_id

        return params

    @backoff(
        exceptions=(ConnectionError, Timeout),
        base_delay=config.clickhouse.backoff_base_delay,
        expo_factor=config.clickhouse.backoff_expo_factor,
        max_tries=config.clickhouse.backoff_max_tries,
        jitter=config.clickhouse.backoff_jitter,
    )
    def execute(self, query: str) -> Response | None:
        url = f"{self.proto}://{self.host}:{self.port}"
        params = self._prepare_query_params()

        try:
            if self.proto == ClickhouseProto.HTTPS:
                response = requests.post(
                    url=url,
                    headers=self.headers,
                    params=params,
                    data=query,
                    timeout=self.timeout,
                    verify=self.cacert,
                )
            else:
                response = requests.post(
                    url=url, headers=self.headers, params=params, data=query, timeout=self.timeout
                )
        except (Timeout, ConnectionError):
            raise
        except Exception as exc:
            logger.exception(f"Could not execute query in Clickhouse: {exc}")
            raise ClickhouseError(exc) from exc
        else:
            if not response.ok:
                msg = f"Could not execute query in Clickhouse. Status: {response.status_code}. {response.text}"
                logger.error(msg)
                raise ClickhouseError(msg)
        return response

    # TODO (akimrx): add sort by partition key (i.e. `updated_at`)? for best insert perfomance
    def insert_batch(self, database: str, table: str, payload: List[Dict]) -> Response | None:
        if not isinstance(payload, list):
            raise ClickhouseError("Payload must be list")

        tags = [f"database:{database}", f"table:{table}"]
        batch_size = len(payload)
        data = " ".join([json.dumps(row) for row in payload])
        logger.debug(f"Inserting batch ({batch_size}): {data}")

        with monitoring.send_time_metric("clickhouse_insert_time_seconds", tags):
            query_result = self.execute(f"INSERT INTO {database}.{table} FORMAT JSONEachRow {data}")

        monitoring.send_gauge_metric("clickhouse_inserted_rows", batch_size, tags)
        return query_result

    def deduplicate(self, database: str, table: str) -> None:
        tags = [f"database:{database}", f"table:{table}"]
        with monitoring.send_time_metric("clickhouse_deduplicate_time_seconds", tags):
            self.execute(f"OPTIMIZE TABLE {database}.{table} FINAL")
