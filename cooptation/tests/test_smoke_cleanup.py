"""Unit test for smoke_test_cooptation._cleanup ordering (T5, 2026-08-01
review tail): the candidate-side SKIP guard returned before the parrain
cleanup ran, stranding SmokeParrain1/2 as active members visible in the
live /annuaire/ until a later successful run."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model

from members.models import Member


@pytest.mark.django_db
def test_cleanup_skip_path_still_removes_parrains(make_member):
    from cooptation.management.commands.smoke_test_cooptation import (
        SMOKE_PARRAIN_1_EMAIL,
        SMOKE_PARRAIN_2_EMAIL,
        Command,
    )

    User = get_user_model()  # noqa: N806

    # A REAL account under the candidate email — no SMOKE marker.
    real_user = User.objects.create_user(
        username="realperson", email="real@example.test", password="x"
    )
    make_member(user=real_user, first_name="Genuine")

    # Stranded smoke parrains from a previous run.
    for i, email in enumerate((SMOKE_PARRAIN_1_EMAIL, SMOKE_PARRAIN_2_EMAIL), start=1):
        u = User.objects.create_user(username=f"smokeparrain{i}", email=email, password="x")
        make_member(user=u, first_name=f"SmokeParrain{i}")

    cmd = Command()
    cmd.stderr = StringIO()
    cmd.stdout = StringIO()
    cmd._cleanup("real@example.test")

    # The real account is untouched...
    assert User.objects.filter(email="real@example.test").exists()
    assert Member.objects.filter(user=real_user).exists()
    # ...and the stranded parrains are gone despite the SKIP.
    assert not User.objects.filter(email=SMOKE_PARRAIN_1_EMAIL).exists()
    assert not User.objects.filter(email=SMOKE_PARRAIN_2_EMAIL).exists()
