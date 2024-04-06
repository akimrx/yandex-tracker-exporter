import os
import logging

from abc import ABC, abstractmethod
from typing import Any, ContextManager

import boto3

from tracker_exporter.state.serializers import AbstractSerializer, JsonSerializer

logger = logging.getLogger(__name__)


class AbstractFileStorageBackend(ABC):
    """
    An abstract base class for file storage systems, enforcing a common interface for file operations.

    :param serializer: The serializer instance used for serializing and deserializing data.
    :param raise_if_not_exists: Raise :exc:`FileNotFound` if file not exists. Defaults to True.
    :param auto_sub_ext_by_serializer: Automatically substitute the file extension based on the serializer. Defaults is ``False``.

    """

    def __init__(
        self,
        serializer: AbstractSerializer,
        raise_if_not_exists: bool = True,
        auto_sub_ext_by_serializer: bool = False,
    ) -> None:
        self.serializer = serializer if hasattr(serializer, "is_initialized") else serializer()
        self.raise_if_not_exists = raise_if_not_exists
        self.auto_sub_ext_by_serializer = auto_sub_ext_by_serializer

    def path_with_ext(self, path: str) -> str:
        """Appends the file extension from the serializer if not present in the path."""
        if not path.endswith(f".{self.serializer.ext}"):
            return f"{path}.{self.serializer.ext}"
        return path

    @abstractmethod
    def read(self, path: str, deserialize: bool = False) -> Any:
        """Abstract method for reading data from a given file path."""

    @abstractmethod
    def write(self, path: str, data: Any) -> None:
        """Abstract method for writing data to a given file path."""


class AbstractKeyValueStorageBackend(ABC):
    """An abstract base class for key value storage backends like Redis, Consul, etc."""

    @abstractmethod
    def client(self, *args, **kwargs) -> ContextManager:
        """An abstract method that returns client context manager."""

    @abstractmethod
    def get(self, key: str | list, *args, **kwargs) -> Any:
        """An abstract method for get value(s) by key from storage."""

    @abstractmethod
    def set(self, key: str, value: Any, *args, **kwargs) -> None:
        """An abstract method for save key:value pair to storage."""

    @abstractmethod
    def delete(self, key: str | list, *args, **kwargs) -> None:
        """An abstract method for deletes key(s) from storage."""


class LocalFileStorageBackend(AbstractFileStorageBackend):
    """
    A concrete synchronous implementation of AbstractFileStorage for local file storage operations.
    Overrides the read and write asynchronous methods for file operations using the aiofiles package.

    :param serializer: The serializer instance used for serializing and deserializing data.
    :param raise_if_not_exists: Raise :exc:`FileNotFound` if file not exists. Defaults to True.
    :param auto_sub_ext_by_serializer: Automatically substitute the file extension based on the serializer. Defaults is ``False``.

    Default serializer: :class:`JsonSerializer`

    Usage::

        storage = LocalFileStorage()

        storage.write("myfile.json", data={"foo": "bar"})
        r = storage.read("myfile.json", deserialize=True)

        print(r)  # {"foo": "bar"}

    """

    def __init__(
        self,
        serializer: AbstractSerializer | None = None,
        raise_if_not_exists: bool = True,
        auto_sub_ext_by_serializer: bool = False,
    ) -> None:
        super().__init__(
            serializer or JsonSerializer,
            raise_if_not_exists=raise_if_not_exists,
            auto_sub_ext_by_serializer=auto_sub_ext_by_serializer,
        )

    def read(self, path: str, deserialize: bool = False) -> Any:
        """
        Reads data from a local file, deserializes it using the provided serializer,
        and returns the deserialized data.

        :param path: A local file path for read content from.
        :param deserialize: Deserialize readed file content via serializer.

        """
        if self.auto_sub_ext_by_serializer:
            path = self.path_with_ext(path)

        if not os.path.isfile(path) and not os.path.exists(path):
            if self.raise_if_not_exists:
                raise FileNotFoundError(f"File with name {path} not found")
            logger.debug(f"File with name '{path}' not found")
            return {}

        with open(path, "r") as file:
            data = file.read()

        if deserialize:
            return self.serializer.deserialize(data)
        return data

    def write(self, path: str, data: Any) -> None:
        """
        Serializes the given data using the provided serializer and writes it to a local file.

        :param path: An local path for write content to.
        :param data: Content that will be written to file.

        """

        if self.auto_sub_ext_by_serializer:
            path = self.path_with_ext(path)

        with open(path, "w") as file:
            file.write(self.serializer.serialize(data))


class S3FileStorageBackend(AbstractFileStorageBackend):
    """
    A concrete synchronous implementation of AbstractFileStorage for S3 object storage operations.
    Initializes an aioboto3 session and provides read and write operations for files stored in an S3 bucket.

    Default serializer: :class:`JsonSerializer`

    :param bucket_name: The name of the S3 bucket.
    :param access_key_id: Service account ID, if empty using ``AWS_ACCESS_KEY_ID`` environment variable.
    :param secret_key: Secret key for service account, if empty using ``AWS_SECRET_ACCESS_KEY`` environment variable.
    :param endpoint_url: S3 endpoint for use with Yandex.Cloud, Minio and other providers.
    :param region: S3 region. Default: ``us-east1``
    :param serializer: The serializer instance used for serializing and deserializing data.
    :param raise_if_not_exists: Raise FileNotFound if file not exists. Defaults to ``True``.
    :param auto_sub_ext_by_serializer: Automatically substitute the file extension based on the serializer. Defaults is ``False``.

    Usage::

        storage = S3FileStorage(
            bucket_name="my-bucket",
            access_key_id="XXXX",
            secret_key="XXXX",
            endpoint_url="https://storage.yandexcloud.net",
            region="ru-central1"
        )

        storage.write("myfile.json", data={"foo": "bar"})
        r = storage.read("myfile.json", deserialize=True)

        print(r)  # {"foo": "bar"}

    """

    def __init__(
        self,
        bucket_name: str,
        serializer: AbstractSerializer | None = None,
        raise_if_not_exists: bool = True,
        auto_sub_ext_by_serializer: bool = False,
        access_key_id: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            serializer or JsonSerializer,
            raise_if_not_exists=raise_if_not_exists,
            auto_sub_ext_by_serializer=auto_sub_ext_by_serializer,
        )
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_key,
            region_name=region or "us-east1",
            **kwargs,
        )

    @property
    def client(self):
        """Returns a resource client for S3 operations."""
        return self.session.client("s3", endpoint_url=self.endpoint_url)

    def read(self, path: str, deserialize: bool = False) -> Any:
        """
        Reads data from an S3 object, deserializes it using the provided serializer,
        and returns the deserialized data.

        :param path: A local file path for read content from.
        :param deserialize: Deserialize readed file content via serializer.

        """
        if self.auto_sub_ext_by_serializer:
            path = self.path_with_ext(path)

        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=path)
        except Exception as exc:
            error_msg = f"Exception while reading file '{path}'. Possible file not exists. Error: {exc}"

            if self.raise_if_not_exists:
                raise FileNotFoundError(error_msg) from exc

            logger.debug(error_msg)
            return {}

        with response["Body"] as stream:
            data = stream.read()

        if deserialize:
            return self.serializer.deserialize(data.decode())
        return data.decode()

    def write(self, path: str, data: Any) -> None:
        """
        Serializes the given data using the provided serializer and writes it to an S3 object.

        :param path: An local path for write content to.
        :param data: Content that will be written to file.

        """
        if self.auto_sub_ext_by_serializer:
            path = self.path_with_ext(path)

        self.client.put_object(Bucket=self.bucket_name, Key=path, Body=self.serializer.serialize(data).encode())


__all__ = [
    "AbstractFileStorageBackend",
    "LocalFileStorageBackend",
    "S3FileStorageBackend",
]
