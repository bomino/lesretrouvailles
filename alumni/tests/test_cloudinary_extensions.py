"""Tests for the P5a additions to alumni/cloudinary.py:
- upload_file() on FakeCloudinary (deterministic stub)
- memory_thumbnail_url() / memory_full_url() URL shape."""

from __future__ import annotations

import io
from io import BytesIO

from PIL import Image

from alumni.cloudinary import (
    _strip_exif_metadata,
    memory_full_url,
    memory_thumbnail_url,
)


class TestStripExifMetadata:
    def _make_jpeg_with_exif(self) -> BytesIO:
        """Build a tiny in-memory JPEG that has a recognisable EXIF tag."""
        img = Image.new("RGB", (10, 10), color="red")
        exif = img.getexif()
        # 0x010E is the standard ImageDescription tag — easy to assert against.
        exif[0x010E] = "test exif description"
        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        buf.seek(0)
        return buf

    def test_exif_present_in_unstripped_baseline(self):
        # Sanity: confirm our fixture actually carries EXIF.
        buf = self._make_jpeg_with_exif()
        roundtrip = Image.open(buf)
        assert roundtrip.getexif().get(0x010E) == "test exif description"

    def test_strip_removes_exif_from_jpeg(self):
        buf = self._make_jpeg_with_exif()
        stripped = _strip_exif_metadata(buf, content_type="image/jpeg")
        stripped_img = Image.open(stripped)
        assert dict(stripped_img.getexif()) == {}

    def test_strip_preserves_image_dimensions(self):
        buf = self._make_jpeg_with_exif()
        stripped = _strip_exif_metadata(buf, content_type="image/jpeg")
        stripped_img = Image.open(stripped)
        assert stripped_img.size == (10, 10)

    def test_strip_falls_back_to_original_on_pillow_failure(self, caplog):
        # Random bytes Pillow cannot decode → fall back to original.
        bogus = BytesIO(b"not-an-image-at-all")
        result = _strip_exif_metadata(bogus, content_type="image/jpeg")
        assert result.read() == b"not-an-image-at-all"
        assert "EXIF strip failed" in caplog.text

    def test_strip_passes_through_unsupported_content_type(self):
        # image/gif is not in _STRIPPABLE_MIME_TYPES — should return bytes unchanged.
        data = b"some-gif-bytes"
        result = _strip_exif_metadata(BytesIO(data), content_type="image/gif")
        assert result.read() == data

    def test_strip_rewinds_already_consumed_file_obj(self):
        """Regression: `_strip_exif_metadata` did `file_obj.read()` without
        first seeking to 0. If any upstream caller (validation, virus scan,
        future content-type sniffer) had already read the buffer, Pillow
        would receive zero bytes → UnidentifiedImageError → empty fallback
        → Cloudinary rejects the upload with no useful error context. Seek
        defensively before reading so the strip path is robust to upstream
        consumption."""
        buf = self._make_jpeg_with_exif()
        # Simulate an upstream consumer that left the cursor at EOF.
        buf.read()
        assert buf.tell() > 0

        stripped = _strip_exif_metadata(buf, content_type="image/jpeg")

        # Should produce a valid stripped JPEG, not an empty BytesIO.
        stripped_img = Image.open(stripped)
        assert stripped_img.size == (10, 10)
        assert dict(stripped_img.getexif()) == {}


class TestMemoryUrlExifStripFlag:
    def test_thumbnail_url_contains_fl_strip_profile(self):
        url = memory_thumbnail_url("memoires/sample", size=200)
        assert "fl_strip_profile" in url

    def test_full_url_contains_fl_strip_profile(self):
        url = memory_full_url("memoires/sample", max_width=1200)
        assert "fl_strip_profile" in url


def test_fake_cloudinary_upload_file_returns_deterministic_public_id():
    from alumni.cloudinary import FakeCloudinary

    client = FakeCloudinary()
    file_obj = io.BytesIO(b"fake-image-bytes")
    file_obj.name = "test.jpg"

    result = client.upload_file(file_obj, folder="memoires")

    assert result.startswith("memoires/")
    # Same input → same output
    file_obj_2 = io.BytesIO(b"fake-image-bytes")
    file_obj_2.name = "test.jpg"
    assert client.upload_file(file_obj_2, folder="memoires") == result
    # Different name → different public_id
    file_obj_3 = io.BytesIO(b"x")
    file_obj_3.name = "other.jpg"
    assert client.upload_file(file_obj_3, folder="memoires") != result


def test_fake_cloudinary_records_upload_calls():
    from alumni.cloudinary import FakeCloudinary

    client = FakeCloudinary()
    file_obj = io.BytesIO(b"data")
    file_obj.name = "photo.jpg"

    client.upload_file(file_obj, folder="memoires")

    assert len(client.upload_calls) == 1
    assert client.upload_calls[0]["folder"] == "memoires"
    assert client.upload_calls[0]["name"] == "photo.jpg"


def test_memory_thumbnail_url_uses_correct_transform(settings):
    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    from alumni.cloudinary import memory_thumbnail_url

    url = memory_thumbnail_url("memoires/abc123", size=400)

    assert url == (
        "https://res.cloudinary.com/test-cloud/image/upload/"
        "f_auto,q_auto:eco,fl_strip_profile,c_fill,g_auto,w_400,h_400/memoires/abc123"
    )


def test_memory_thumbnail_url_returns_empty_for_blank_public_id():
    from alumni.cloudinary import memory_thumbnail_url

    assert memory_thumbnail_url("") == ""


def test_memory_full_url_uses_limit_fit_no_crop(settings):
    settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
    from alumni.cloudinary import memory_full_url

    url = memory_full_url("memoires/abc123", max_width=1200)

    assert url == (
        "https://res.cloudinary.com/test-cloud/image/upload/"
        "f_auto,q_auto:eco,fl_strip_profile,c_limit,w_1200/memoires/abc123"
    )


def test_real_cloudinary_init_loads_required_submodules():
    """RealCloudinary's methods reference cloudinary.api, cloudinary.uploader,
    and cloudinary.utils. `import cloudinary` does NOT transitively pull in
    api/uploader, so __init__ must import them explicitly. This test catches
    future regressions where someone deletes one of those imports — without
    it, the bug only surfaces in prod the first time the broken codepath
    runs (e.g. uploading the first real photo)."""
    import cloudinary

    from alumni.cloudinary import RealCloudinary

    # Construct (calls __init__, which performs the imports)
    RealCloudinary()

    # All three submodules must be present after init
    assert hasattr(cloudinary, "api"), (
        "cloudinary.api not loaded — RealCloudinary.download() will crash"
    )
    assert hasattr(cloudinary, "uploader"), (
        "cloudinary.uploader not loaded — RealCloudinary.upload_file() / .delete() will crash"
    )
    assert hasattr(cloudinary, "utils"), (
        "cloudinary.utils not loaded — RealCloudinary.sign_upload() will crash"
    )
    # And the actual callables we use must resolve
    assert callable(cloudinary.api.resource)
    assert callable(cloudinary.uploader.upload)
    assert callable(cloudinary.uploader.destroy)
    assert callable(cloudinary.utils.api_sign_request)


class TestExifOrientation:
    """Android cameras — the target audience's devices — record rotation in
    the EXIF Orientation tag and store sensor-native pixels. Dropping the
    tag without baking the rotation into the pixels uploads every portrait
    photo sideways, and g_face cropping then misses the face."""

    def _portrait_jpeg_with_orientation_6(self) -> BytesIO:
        # 20 wide x 10 tall on disk; Orientation=6 means "rotate 90° CW to
        # display", so the intended display size is 10 wide x 20 tall.
        img = Image.new("RGB", (20, 10), color="blue")
        exif = img.getexif()
        exif[0x0112] = 6  # Orientation
        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        buf.seek(0)
        return buf

    def test_strip_bakes_orientation_into_pixels(self):
        from alumni.cloudinary import _strip_exif_metadata

        buf = self._portrait_jpeg_with_orientation_6()
        assert Image.open(buf).size == (20, 10)  # sensor-native, pre-strip
        buf.seek(0)

        result = _strip_exif_metadata(buf, content_type="image/jpeg")
        out = Image.open(result)
        assert out.size == (10, 20), (
            "pixels must be transposed to display orientation before EXIF is dropped"
        )
        assert out.getexif().get(0x0112) is None  # tag still gone
