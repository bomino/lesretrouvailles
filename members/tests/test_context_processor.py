import pytest
from django.test import RequestFactory

from members.context import member_preferences


@pytest.mark.django_db
def test_anonymous_request_returns_empty_prefs():
    rf = RequestFactory()
    req = rf.get("/")
    from django.contrib.auth.models import AnonymousUser

    req.user = AnonymousUser()
    ctx = member_preferences(req)
    assert ctx["member_prefs"] is None


@pytest.mark.django_db
def test_authenticated_member_request_exposes_prefs(make_member, make_user):
    user = make_user(password="x")
    member = make_member(user=user)
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    ctx = member_preferences(req)
    assert ctx["member_prefs"] is not None
    assert ctx["member_prefs"].pk == member.preferences.pk


@pytest.mark.django_db
def test_template_can_read_data_saver(make_member, make_user):
    from django.template import RequestContext, Template

    user = make_user(password="x")
    member = make_member(user=user)
    member.preferences.data_saver = True
    member.preferences.save()
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user
    rc = RequestContext(req, {})
    tmpl = Template("{% if member_prefs.data_saver %}YES{% else %}NO{% endif %}")
    assert tmpl.render(rc).strip() == "YES"
