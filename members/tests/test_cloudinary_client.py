from django.test import override_settings

from alumni.cloudinary import FakeCloudinary, get_client, member_thumbnail_url


def test_fake_cloudinary_records_sign_calls():
    fake = FakeCloudinary()
    out = fake.sign_upload(folder="members/abc/", timestamp=1700000000)
    assert out["folder"] == "members/abc/"
    assert out["signature"].startswith("fake-sig-")
    assert fake.sign_calls == [{"folder": "members/abc/", "timestamp": 1700000000}]


def test_fake_cloudinary_records_delete_calls():
    fake = FakeCloudinary()
    fake.delete("members/abc/photo123")
    assert fake.delete_calls == ["members/abc/photo123"]


@override_settings(CLOUDINARY_CLIENT_PATH="alumni.cloudinary.FakeCloudinary")
def test_get_client_returns_fake_when_configured():
    client = get_client()
    assert isinstance(client, FakeCloudinary)


def test_member_thumbnail_url_includes_lazy_transform():
    url = member_thumbnail_url("members/abc/photo123", size=240)
    assert "f_auto" in url
    assert "q_auto:eco" in url
    assert "w_240" in url
    assert "h_240" in url
    assert "/members/abc/photo123" in url


def test_member_thumbnail_url_handles_blank_public_id():
    assert member_thumbnail_url("") == ""
