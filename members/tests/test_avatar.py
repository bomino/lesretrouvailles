import re

import pytest

from members.templatetags.member_avatar import (
    avatar_hue_for_slug,
    initials_for_member,
)


@pytest.mark.django_db
def test_initials_uses_first_letter_of_each_name(make_member):
    m = make_member(first_name="Idrissa", last_name="Saidou")
    assert initials_for_member(m) == "IS"


@pytest.mark.django_db
def test_initials_uppercased(make_member):
    m = make_member(first_name="idrissa", last_name="saidou")
    assert initials_for_member(m) == "IS"


def test_avatar_hue_is_deterministic_for_same_slug():
    s = "11111111-1111-1111-1111-111111111111"
    assert avatar_hue_for_slug(s) == avatar_hue_for_slug(s)


def test_avatar_hue_distributes_across_slugs():
    hues = {avatar_hue_for_slug(f"slug-{i}") for i in range(50)}
    assert len(hues) > 25  # rough distribution check


def test_avatar_hue_is_in_valid_range():
    h = avatar_hue_for_slug("any-slug")
    assert 0 <= h < 360


@pytest.mark.django_db
def test_member_avatar_renders_initials_when_no_photo(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace")
    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m}))
    assert "AL" in out
    assert re.search(r"hsl\(\d+,\s*55%,\s*45%\)", out)
    assert "<img" not in out


@pytest.mark.django_db
def test_member_avatar_renders_image_when_photo_set(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace", photo_public_id="members/abc/photo1")
    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m}))
    assert "<img" in out
    assert "members/abc/photo1" in out


@pytest.mark.django_db
def test_member_avatar_falls_back_to_initials_when_viewer_has_data_saver(make_member):
    from django.template import Context, Template

    m = make_member(first_name="Ada", last_name="Lovelace", photo_public_id="members/abc/photo1")

    class FakePrefs:
        data_saver = True

    tmpl = Template("{% load member_avatar %}{% member_avatar member size=48 %}")
    out = tmpl.render(Context({"member": m, "member_prefs": FakePrefs()}))
    assert "<img" not in out
    assert "AL" in out
