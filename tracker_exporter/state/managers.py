from abc import ABC, abstractmethod
from contextlib import suppress
from typing import Any, Type

from tracker_exporter.state.backends import AbstractFileStorageBackend, AbstractKeyValueStorageBackend
from tracker_exporter.state.serializers import AbstractSerializer, JsonSerializer
from tracker_exporter.exceptions import SerializerError


class AbstractStateManager(ABC):
    """
    Abstract class for state storage.

    Allows user to async save, receive, delete and flush the state.
    """

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        """Abstract method for save key:value pair to storage."""

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """Abstract method for get value by key from storage."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Abstract method for delete value by key from storage."""

    @abstractmethod
    async def flush(self) -> None:
        """Abstract method for flush (drop) state from storage."""


class FileStateManager(AbstractStateManager):
    """
    A state manager for handling state persistence in file storage (local, s3 or other).

    This class provides an abstraction for managing application state data stored within a file.
    It supports basic CRUD operations such as setting, getting, and deleting state information,
    utilizing an abstract file storage mechanism.

    :param storage: The file storage provider for persisting state data.
    :param state_file_name: The name of the file where state data is stored. Defaults to ``state``.

    Usage::

        from datetime import datetime

        storage_backend = LocalFileStorage()  # also, you can use S3FileStorage
        state = FileStateManager(storage_backend, state_file_name="my_state")


        def my_function() -> None:
            ...
            last_state = state.get("my_function", default={})

            if last_state.get("last_run") is None:
                new_state = {"last_run": datetime.now().strftime("%Y-%M-%d %H:%M:%S")}
                state.set("myfunction", new_state)

                ...

    .. note::
        The state data is managed as a dictionary (JSON-compatible), allowing for key-value pair manipulation.
        Other data formats is NOT SUPPORTED.

    """

    def __init__(self, storage: AbstractFileStorageBackend, state_file_name: str = "state") -> None:
        self.storage = storage
        self.state_file_name = state_file_name
        self.state = {}

        self.storage.auto_sub_ext_by_serializer = True
        self.storage.raise_if_not_exists = False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get state value by key.

        :param key: State key.
        :param default: Default value if specified key not found.

        """
        self.state = self.storage.read(self.state_file_name, deserialize=True)
        return self.state.get(key, default)

    def set(self, key: str, value: str) -> None:
        """
        Set state an value for the key.

        :param key: State key.
        :param value: Value to be saved assotiated with key.

        """
        self.state = self.storage.read(self.state_file_name, deserialize=True)
        self.state[key] = value
        self.storage.write(self.state_file_name, self.state)

    def delete(self, key: str) -> None:
        """

        Deletes state (value) by key.

        :param key: State key to be deleted.
        """
        self.state = self.storage.read(self.state_file_name, deserialize=True)
        if self.state.get(key) is not None:
            del self.state[key]
            self.storage.write(self.state_file_name, self.state)

    def flush(self):
        """Drop all data from state."""
        self.state = {}
        self.storage.write(self.state_file_name, self.state)


class RedisStateManager(AbstractStateManager):
    """
    A state manager for handling state persistence in the Redis storage.

    This class provides an abstraction layer over a Redis storage mechanism, allowing
    for easy setting, getting, and deletion of state information with optional serialization
    support. It uses an underlying key-value storage provider and supports namespacing to
    segregate different state data.

    It is recommended to use a JSON-compatible state format, such as a dict, to maintain portability
    between other state managers.

    :param storage: The storage provider for persisting state data.
    :param serializer: An optional serializer for converting
                data to and from the storage format. Defaults to JsonSerializer if not provided.
    :param namespace: A namespace prefix for all keys managed by this instance.
                Helps in avoiding key collisions. Defaults to ``tracker_exporter_default``.

    Usage::

        from datetime import datetime
        from redis import Redis

        redis = Redis.from_url("redis://localhost:6379", decode_responses=True)
        state = RedisStateManager(redis, namespace="my_namespace")


        def my_function() -> None:
            ...
            last_state = state.get("my_function", default={})

            if last_state.get("last_run") is None:
                new_state = {"last_run": datetime.now().strftime("%Y-%M-%d %H:%M:%S")}
                state.set("myfunction", new_state)

                ...

    """

    def __init__(
        self,
        storage: AbstractKeyValueStorageBackend,
        serializer: Type[AbstractSerializer] | None = None,
        namespace: str = "tracker_exporter_default",
    ) -> None:
        self.storage = storage
        self.serializer = serializer() or JsonSerializer()
        self.namespace = namespace

    def _rkey(self, key: str) -> str:
        """Resolve full key path with namespace."""
        return f"{self.namespace}:{key}"

    def set(self, key: str, value: Any) -> None:
        """
        Set an value for the state key.

        :param key: State key.
        :param value: Value to be saved assotiated with key.

        """
        if isinstance(value, dict):
            value = self.serializer.serialize(value)

        with self.storage.client() as session:
            session.set(self._rkey(key), value)

    def get(self, key: str) -> Any:
        """
        Get state value by key from Redis.

        :param key: Key state.
        :param default: Default value if specified key not found.

        """
        with self.storage.client() as session:
            value = session.get(self._rkey(key))

        with suppress(SerializerError):
            value = self.serializer.deserialize(value)
        return value

    def delete(self, key: str) -> None:
        """
        Deletes state (value) by key if exists.

        :param key: State key to be deleted.
        """
        with self.storage.client() as session:
            session.delete(self._rkey(key))

    def flush(self) -> None:
        """Flush all data in the namespace."""
        raise NotImplementedError

    def execute(self, cmd: str, *args, **kwargs) -> Any:
        """
        Common method for execute any Redis supported command.

        :param cmd: Redis command to execute.
        """
        with self.storage.client() as session:
            return session.execute_command(cmd, *args, **kwargs)


__all__ = ["AbstractStateManager", "FileStateManager", "RedisStateManager"]
