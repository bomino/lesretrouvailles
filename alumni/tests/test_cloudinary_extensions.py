"""Tests for the P5a additions to alumni/cloudinary.py:
- upload_file() on FakeCloudinary (deterministic stub)
- memory_thumbnail_url() / memory_full_url() URL shape."""

from __future__ import annotations

import io


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
        "f_auto,q_auto:eco,c_fill,g_auto,w_400,h_400/memoires/abc123"
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
        "f_auto,q_auto:eco,c_limit,w_1200/memoires/abc123"
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
