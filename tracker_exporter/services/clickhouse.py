import json
import logging

from typing import List, Dict, Union

from requests import Response
import requests

from tracker_exporter.errors import ClickhouseError, NetworkError, TimedOut
from tracker_exporter.utils.helpers import retry
from tracker_exporter.services.monitoring import DogStatsdClient
from tracker_exporter.models.enums import ClickhouseProto
from tracker_exporter.defaults import (
    CLICKHOUSE_PROTO,
    CLICKHOUSE_CACERT_PATH,
    CLICKHOUSE_SERVERLESS_PROXY_ID
)

logger = logging.getLogger(__name__)
monitoring = DogStatsdClient()


class ClickhouseClient:
    """This class provide simple facade interface for Clickhouse."""

    def __init__(self,  # pylint: disable=W0102
                 host: str,
                 port: int = 8123,
                 user: str = "default",
                 password: str = None,
                 proto: ClickhouseProto = CLICKHOUSE_PROTO,
                 cacert: str = CLICKHOUSE_CACERT_PATH,
                 serverless_proxy_id: str = CLICKHOUSE_SERVERLESS_PROXY_ID,
                 params: dict = {},
                 http_timeout: int = 10) -> None:

        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.proto = proto
        self.cacert = cacert
        self.serverless_proxy_id = serverless_proxy_id
        self.params = params
        self.timeout = int(http_timeout)
        self.headers = {"Content-Type": "application/json"}

        if self.proto == ClickhouseProto.HTTPS:
            assert self.cacert is not None

    @retry((NetworkError, TimedOut))
    def execute(self, query: str) -> Union[None, Response]:
        url = f"{self.proto}://{self.host}:{self.port}"

        if self.proto != ClickhouseProto.HTTPS:
            url += f"?user={self.user}"
            if self.password is not None:
                url += f"&password={self.password}"
        else:
            self.headers["X-Clickhouse-User"] = self.user
            self.headers["X-Clickhouse-Key"] = self.password

        if self.serverless_proxy_id:
            self.params["database"] = self.serverless_proxy_id

        if self.params:
            params = "&".join([f"{k}={v}" for k, v in self.params.items()])
            url += f"&{params}" if self.proto != ClickhouseProto.HTTPS else f"?{params}"

        try:
            if self.proto == ClickhouseProto.HTTPS:
                response = requests.post(
                    url=url, headers=self.headers, data=query,
                    timeout=self.timeout, verify=self.cacert
                )
            else:
                response = requests.post(
                    url=url, headers=self.headers, data=query, timeout=self.timeout
                )
        except requests.Timeout as exc:
            raise TimedOut() from exc
        except requests.ConnectionError as exc:
            raise NetworkError(exc) from exc
        except Exception as exc:
            logger.exception(
                f"Could not execute query in Clickhouse: {exc}"
            )
            raise ClickhouseError(exc) from exc
        else:
            if not response.ok:
                msg = (
                    f"Could not execute query in Clickhouse. "
                    f"Status: {response.status_code}. {response.text}"
                )
                logger.error(msg)
                raise ClickhouseError(msg)
        return response

    # TODO: add sort by partition key (i.e. `updated_at`) for best insert perfomance
    @monitoring.send_time_metric("clickhouse_insert_time_seconds")
    def insert_batch(self, database: str, table: str, payload: List[Dict]) -> Union[None, Response]:
        if not isinstance(payload, list):
            raise ClickhouseError("Payload must be list")

        _tags = [f"database:{database}", f"table:{table}"]
        data = " ".join([json.dumps(row) for row in payload])
        logger.debug(f"Inserting batch: {data}")
        query_result = self.execute(f"INSERT INTO {database}.{table} FORMAT JSONEachRow {data}")
        monitoring.send_gauge_metric("clickhouse_inserted_rows", len(payload), _tags)
        return query_result

    @monitoring.send_time_metric("clickhouse_deduplicate_time_seconds")
    def deduplicate(self, database: str, table: str) -> Union[None, Response]:
        return self.execute(f"OPTIMIZE TABLE {database}.{table} FINAL")
