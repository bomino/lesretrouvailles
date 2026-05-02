"""Cloudinary integration: real client, test fake, and lazy URL helpers."""

from __future__ import annotations

import hashlib
import time
from importlib import import_module
from typing import Any, Protocol

from django.conf import settings


class CloudinaryClient(Protocol):
    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]: ...

    def delete(self, public_id: str) -> None: ...


class RealCloudinary:
    """Production client wrapping the `cloudinary` SDK."""

    def __init__(self) -> None:
        import cloudinary  # noqa: WPS433

        cloudinary.config(secure=True)
        self._cloudinary = cloudinary

    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]:
        api_key = self._cloudinary.config().api_key
        api_secret = self._cloudinary.config().api_secret
        params = {"folder": folder, "timestamp": timestamp}
        signature = self._cloudinary.utils.api_sign_request(params, api_secret)
        return {
            "api_key": api_key,
            "timestamp": timestamp,
            "signature": signature,
            "folder": folder,
            "max_file_size": 5 * 1024 * 1024,
            "allowed_formats": ["jpg", "jpeg", "png", "webp"],
        }

    def delete(self, public_id: str) -> None:
        if not public_id:
            return
        self._cloudinary.uploader.destroy(public_id, invalidate=True)


class FakeCloudinary:
    """In-memory client used in tests. Records calls; never hits the network."""

    def __init__(self) -> None:
        self.sign_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []

    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]:
        self.sign_calls.append({"folder": folder, "timestamp": timestamp})
        digest = hashlib.sha1(f"{folder}:{timestamp}".encode()).hexdigest()[:16]
        return {
            "api_key": "fake-key",
            "timestamp": timestamp,
            "signature": f"fake-sig-{digest}",
            "folder": folder,
            "max_file_size": 5 * 1024 * 1024,
            "allowed_formats": ["jpg", "jpeg", "png", "webp"],
        }

    def delete(self, public_id: str) -> None:
        self.delete_calls.append(public_id)


def get_client() -> CloudinaryClient:
    """Resolve the Cloudinary client from settings."""
    path = getattr(settings, "CLOUDINARY_CLIENT_PATH", "alumni.cloudinary.RealCloudinary")
    module_name, _, class_name = path.rpartition(".")
    module = import_module(module_name)
    cls = getattr(module, class_name)
    return cls()


def now_timestamp() -> int:
    return int(time.time())


def member_thumbnail_url(public_id: str, size: int = 240) -> str:
    """Build a lazy Cloudinary URL with f_auto, q_auto:eco, and a square crop."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_face,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
