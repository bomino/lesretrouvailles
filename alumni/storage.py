"""S3-compatible object storage client wrapper.

Real (boto3-backed) + Fake (in-memory) + settings-resolved get_client()
with a singleton FakeStorage in test mode. Mirrors the pattern in
alumni.cloudinary so they're reasoned about identically.

Used by P6a (media backup to a Railway-native bucket) and by P6b's
RGPD purge script (list_versions + delete_version).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Protocol

from django.conf import settings


class StorageClient(Protocol):
    def head_file(self, path: str) -> dict[str, Any] | None: ...

    def upload_file(self, path: str, content: bytes) -> str: ...

    def list_versions(self, prefix: str) -> list[dict[str, Any]]: ...

    def delete_version(self, path: str, file_id: str) -> None: ...


class RealStorage:
    """Production client wrapping boto3's S3 API.

    Lazy-imports boto3 so test environments and the web service don't pay
    the import cost (the cron service is the only place this runs).
    """

    def __init__(self) -> None:
        import boto3  # noqa: WPS433
        from botocore.config import Config  # noqa: WPS433

        self._bucket_name = settings.STORAGE_BUCKET_NAME
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT_URL,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
            region_name=settings.STORAGE_REGION,
            config=Config(signature_version="s3v4"),
        )

    def head_file(self, path: str) -> dict[str, Any] | None:
        from botocore.exceptions import ClientError  # noqa: WPS433

        try:
            resp = self._client.head_object(Bucket=self._bucket_name, Key=path)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return {
            "file_id": resp.get("VersionId", ""),
            "size": resp["ContentLength"],
        }

    def upload_file(self, path: str, content: bytes) -> str:
        resp = self._client.put_object(Bucket=self._bucket_name, Key=path, Body=content)
        return resp.get("VersionId", "")

    def list_versions(self, prefix: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        paginator = self._client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=self._bucket_name, Prefix=prefix):
            for v in page.get("Versions", []):
                out.append(
                    {
                        "file_id": v.get("VersionId", ""),
                        "path": v["Key"],
                        "size": v["Size"],
                    },
                )
        return out

    def delete_version(self, path: str, file_id: str) -> None:
        kwargs = {"Bucket": self._bucket_name, "Key": path}
        if file_id:
            kwargs["VersionId"] = file_id
        self._client.delete_object(**kwargs)


class FakeStorage:
    """In-memory storage client for tests. Records every call. Behaves
    consistently across head/upload/list/delete so test assertions can
    chain them naturally."""

    def __init__(self) -> None:
        self._files: dict[str, dict[str, Any]] = {}
        self._versions: list[dict[str, Any]] = []
        self.upload_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, str]] = []

    def head_file(self, path: str) -> dict[str, Any] | None:
        existing = self._files.get(path)
        if existing is None:
            return None
        return {"file_id": existing["file_id"], "size": existing["size"]}

    def upload_file(self, path: str, content: bytes) -> str:
        file_id = f"fake-{len(self._versions):08d}"
        record = {
            "file_id": file_id,
            "path": path,
            "size": len(content),
            "content": content,
        }
        self._files[path] = record
        self._versions.append(record)
        self.upload_calls.append({"path": path, "size": len(content)})
        return file_id

    def list_versions(self, prefix: str) -> list[dict[str, Any]]:
        return [
            {"file_id": v["file_id"], "path": v["path"], "size": v["size"]}
            for v in self._versions
            if v["path"].startswith(prefix)
        ]

    def delete_version(self, path: str, file_id: str) -> None:
        self.delete_calls.append({"path": path, "file_id": file_id})
        self._versions = [
            v for v in self._versions if not (v["path"] == path and v["file_id"] == file_id)
        ]
        live = self._files.get(path)
        if live is not None and live["file_id"] == file_id:
            del self._files[path]


_fake_singleton: FakeStorage | None = None


def get_client() -> StorageClient:
    """Resolve the storage client from settings.

    When FakeStorage is configured (tests/dev), returns a module-level
    singleton so multiple get_client() calls within the same test share
    recorded state. Call reset_fake_client() from a fixture to get a
    fresh instance.
    """
    global _fake_singleton  # noqa: PLW0603
    path = getattr(settings, "STORAGE_CLIENT_PATH", "alumni.storage.RealStorage")
    module_name, _, class_name = path.rpartition(".")
    module = import_module(module_name)
    cls = getattr(module, class_name)
    if cls is FakeStorage:
        if _fake_singleton is None:
            _fake_singleton = FakeStorage()
        return _fake_singleton
    return cls()


def reset_fake_client() -> FakeStorage:
    """Replace the FakeStorage singleton with a fresh instance and return it.

    Call from test fixtures before each test that needs a clean slate.
    """
    global _fake_singleton  # noqa: PLW0603
    _fake_singleton = FakeStorage()
    return _fake_singleton
