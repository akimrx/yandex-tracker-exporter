from typing import Literal, Type, TypedDict, Optional

from redis import Redis

from tracker_exporter.state.serializers import AbstractSerializer, JsonSerializer
from tracker_exporter.state.backends import S3FileStorageBackend, LocalFileStorageBackend
from tracker_exporter.state.managers import FileStateManager, RedisStateManager


class IObjectStorageProps(TypedDict):
    bucket_name: str
    access_key_id: str
    secret_key: str
    region: Optional[str]
    endpoint_url: Optional[str]


class StateManagerFactory:
    """Factory for easy way to create StateManager."""

    @staticmethod
    def create_file_state_manager(
        strategy: Literal["local", "s3"],
        filename: str = "state.json",
        serializer: Type[AbstractSerializer] = JsonSerializer,
        **s3_props: Optional[IObjectStorageProps],
    ) -> FileStateManager:
        match strategy:
            case "local":
                backend = LocalFileStorageBackend(serializer=serializer, raise_if_not_exists=False)
            case "s3":
                bucket_name = s3_props["bucket_name"]
                del s3_props["bucket_name"]

                backend = S3FileStorageBackend(
                    bucket_name, serializer=serializer, raise_if_not_exists=False, **s3_props
                )
            case _:
                raise ValueError("Invalid jsonfile strategy, allowed: s3, local")

        return FileStateManager(backend, state_file_name=filename)

    @staticmethod
    def create_redis_state_manager(
        url: str,
        namespace: str = "tracker_exporter_default",
        serializer: Type[AbstractSerializer] = JsonSerializer,
    ) -> RedisStateManager:
        backend = Redis.from_url(url, decode_responses=True)
        return RedisStateManager(backend, namespace=namespace, serializer=serializer)
