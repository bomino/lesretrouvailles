"""Cloudinary integration: real client, test fake, and lazy URL helpers."""

from __future__ import annotations

import hashlib
import logging
import time
from importlib import import_module
from io import BytesIO
from typing import Any, Protocol

from django.conf import settings

logger = logging.getLogger(__name__)

# MIME types we know how to strip via Pillow's resave.
_STRIPPABLE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _strip_exif_metadata(file_obj: Any, *, content_type: str) -> BytesIO:
    """Re-encode the image via Pillow to drop EXIF/XMP/IPTC from the bytes.

    Pillow's .save() does not preserve metadata unless you pass the exif=
    kwarg explicitly. Calling it without exif= produces a clean copy.

    On any Pillow failure (corrupt file, unsupported format, etc.) we log a
    warning and return the original bytes unchanged. This trades EXIF
    protection on the failing upload for keeping the user-visible upload
    flow working — the photo lands on the wall; the operator can manually
    re-upload if they suspect a problem. The §I Risk #14 residual.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    # Pillow needs a seekable stream. Rewind first in case any upstream
    # caller (validation, virus scan, content-type sniff) already consumed
    # the buffer — otherwise file_obj.read() returns empty bytes and Pillow
    # raises UnidentifiedImageError, dropping us into the empty-fallback
    # path that surfaces as an opaque Cloudinary rejection.
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except (OSError, ValueError):
            pass  # Non-seekable stream; fall through and hope for the best.
    raw = file_obj.read() if hasattr(file_obj, "read") else file_obj
    if isinstance(raw, bytes):
        source = BytesIO(raw)
    else:
        source = BytesIO(bytes(raw))
    source.seek(0)

    if content_type not in _STRIPPABLE_MIME_TYPES:
        # Trust the validation layer; this branch is defensive only.
        source.seek(0)
        return source

    try:
        img = Image.open(source)
        img.load()  # force-decode now so errors fire here, not later
        # Bake the EXIF Orientation rotation into the pixels BEFORE the save
        # drops the tag. Android cameras (this audience's devices) store
        # sensor-native pixels and encode rotation only in that tag — without
        # this, every portrait photo uploads sideways and g_face misses the
        # face. No-op for images without an Orientation tag.
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("EXIF strip failed (Pillow open): %s", exc, exc_info=True)
        source.seek(0)
        return source

    out = BytesIO()
    fmt_map = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }
    pil_format = fmt_map[content_type]

    try:
        # Note: NOT passing exif= drops the EXIF chunk on JPEG.
        # PNG/WebP: Pillow drops ancillary chunks (incl. metadata) by default.
        save_kwargs = {"format": pil_format}
        if pil_format == "JPEG":
            # Preserve original quality reasonably; 95 matches Pillow's "good".
            save_kwargs["quality"] = 95
            save_kwargs["optimize"] = True
        img.save(out, **save_kwargs)
    except (OSError, ValueError) as exc:
        logger.warning("EXIF strip failed (Pillow save): %s", exc, exc_info=True)
        source.seek(0)
        return source

    out.seek(0)
    return out


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
        """Server-side upload via Cloudinary's REST API. Returns the public_id.

        Strips EXIF/XMP/IPTC metadata server-side before passing to Cloudinary
        (see alumni.cloudinary._strip_exif_metadata). On Pillow failure the
        original bytes flow through unchanged — a logged residual, not a
        user-visible error.
        """
        content_type = getattr(file_obj, "content_type", "image/jpeg")
        stripped = _strip_exif_metadata(file_obj, content_type=content_type)
        result = self._cloudinary.uploader.upload(
            stripped,
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
    """Square thumbnail for the gallery grid. Auto crop with subject focus.

    fl_strip_profile drops EXIF/IPTC from the delivered URL — defense in
    depth alongside the server-side strip in RealCloudinary.upload_file.
    """
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,fl_strip_profile,c_fill,g_auto,w_{size},h_{size}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"


def memory_full_url(public_id: str, max_width: int = 1200) -> str:
    """Limit-fit version for the detail page. No crop; preserves aspect ratio.

    fl_strip_profile drops EXIF/IPTC from the delivered URL — defense in
    depth alongside the server-side strip in RealCloudinary.upload_file.
    """
    if not public_id:
        return ""
    cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "fake-cloud")
    transform = f"f_auto,q_auto:eco,fl_strip_profile,c_limit,w_{max_width}"
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{transform}/{public_id}"
