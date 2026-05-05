"""Cloudinary integration: real client, test fake, and lazy URL helpers."""

from __future__ import annotations

import hashlib
import time
from importlib import import_module
from typing import Any, Protocol

from django.conf import settings


class CloudinaryClient(Protocol):
    def sign_upload(self, *, folder: str, timestamp: int) -> dict[str, Any]: ...

    def upload_file(self, file_obj: Any, *, folder: str) -> str: ...

    def delete(self, public_id: str) -> None: ...

    def download(self, public_id: str) -> bytes: ...


class RealCloudinary:
    """Production client wrapping the `cloudinary` SDK."""

    def __init__(self) -> None:
        # `import cloudinary` does NOT transitively pull in cloudinary.api or
        # cloudinary.uploader — they have to be imported explicitly. Without
        # these next two lines, attribute access on the submodules raises
        # AttributeError at first use ("module 'cloudinary' has no attribute
        # 'uploader'") in production. The bug stayed hidden for months because
        # FakeCloudinary doesn't go through the real SDK; it bites whoever
        # tries to upload the first real photo. Pull both in here so every
        # method on this class can rely on them.
        import cloudinary  # noqa: WPS433
        import cloudinary.api  # noqa: F401, WPS433
        import cloudinary.uploader  # noqa: F401, WPS433

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

    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Server-side upload via Cloudinary's REST API. Returns the public_id."""
        result = self._cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            resource_type="image",
            use_filename=False,
        )
        return result["public_id"]

    def delete(self, public_id: str) -> None:
        if not public_id:
            return
        self._cloudinary.uploader.destroy(public_id, invalidate=True)

    def download(self, public_id: str) -> bytes:
        """Fetch the original (untransformed) bytes for a public_id.

        Used by the P6a backup pipeline. Goes via the Cloudinary admin API to
        resolve the secure_url, then downloads via stdlib urllib (no extra
        dependency).
        """
        import urllib.request

        info = self._cloudinary.api.resource(public_id)
        url = info["secure_url"]
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
            return resp.read()


class FakeCloudinary:
    """In-memory client used in tests. Records calls; never hits the network."""

    def __init__(self) -> None:
        self.sign_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []
        self.upload_calls: list[dict[str, Any]] = []
        self.download_calls: list[str] = []

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

    def upload_file(self, file_obj: Any, *, folder: str) -> str:
        """Test stub: records the call and returns a deterministic fake public_id."""
        name = getattr(file_obj, "name", "upload")
        digest = hashlib.sha1(f"{folder}:{name}".encode()).hexdigest()[:12]
        public_id = f"{folder}/fake-{digest}"
        self.upload_calls.append({"folder": folder, "name": name, "public_id": public_id})
        return public_id

    def delete(self, public_id: str) -> None:
        self.delete_calls.append(public_id)

    def download(self, public_id: str) -> bytes:
        """Return deterministic bytes derived from the public_id; record the call."""
        self.download_calls.append(public_id)
        digest = hashlib.sha1(f"download:{public_id}".encode()).digest()
        return digest * 32  # 640 bytes of deterministic content


_fake_singleton: FakeCloudinary | None = None


def get_client() -> CloudinaryClient:
    """Resolve the Cloudinary client from settings.

    When FakeCloudinary is configured (tests), returns a module-level singleton
    so multiple get_client() calls within the same test share recorded state.
    Call reset_fake_client() from a fixture to get a fresh instance.
    """
    global _fake_singleton  # noqa: PLW0603
    path = getattr(settings, "CLOUDINARY_CLIENT_PATH", "alumni.cloudinary.RealCloudinary")
    module_name, _, class_name = path.rpartition(".")
    module = import_module(module_name)
    cls = getattr(module, class_name)
    if cls is FakeCloudinary:
        if _fake_singleton is None:
            _fake_singleton = FakeCloudinary()
        return _fake_singleton
    return cls()


def reset_fake_client() -> FakeCloudinary:
    """Replace the FakeCloudinary singleton with a fresh instance and return it.

    Call from test fixtures before each test that needs a clean slate.
    """
    global _fake_singleton  # noqa: PLW0603
    _fake_singleton = FakeCloudinary()
    return _fake_singleton


def now_timestamp() -> int:
    return int(time.time())


def member_thumbnail_url(public_id: str, size: int = 240) -> str:
    """Build a lazy Cloudinary URL with f_auto, q_auto:eco, and a square crop."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_face,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_thumbnail_url(public_id: str, size: int = 400) -> str:
    """Square thumbnail for the gallery grid. Auto crop with subject focus."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_fill,g_auto,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_full_url(public_id: str, max_width: int = 1200) -> str:
    """Limit-fit version for the detail page. No crop; preserves aspect ratio."""
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,c_limit,w_{max_width}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
