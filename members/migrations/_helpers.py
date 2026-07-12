"""Data-migration functions kept importable so they can be unit-tested.

Migration modules are awkward to import from tests (leading digits in the
module name); putting the callable here lets a test exercise the real function
the migration runs, instead of a copy of it that can drift.
"""

from __future__ import annotations


def hide_contact_by_default(apps, schema_editor):  # noqa: ARG001 — migration signature
    """F-02: flip existing members to opt-IN contact visibility.

    `show_email` / `show_whatsapp` defaulted to True, while guide_membre.md and
    aide/faq.py both told members they were "décoché par défaut". Nobody could
    therefore have made an informed choice to publish — a True value means "the
    old default", not "I opted in" — so the only safe direction is to hide, and
    let members re-enable it themselves in one click (Profil → Modifier).

    `show_city` is deliberately untouched: the docs promise it IS on by default.
    """
    Member = apps.get_model("members", "Member")  # noqa: N806
    Member.objects.filter(show_email=True).update(show_email=False)
    Member.objects.filter(show_whatsapp=True).update(show_whatsapp=False)


def noop_reverse(apps, schema_editor):  # noqa: ARG001 — migration signature
    """Reversing must NOT re-publish everyone's contact details.

    The forward pass is lossy on purpose (we cannot distinguish "explicitly
    opted in" from "never touched it"), so the reverse leaves the values alone
    rather than flipping them back to True and re-exposing people.
    """
    return None
