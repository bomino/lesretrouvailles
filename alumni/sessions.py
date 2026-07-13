"""Shorter sessions for privileged accounts.

SESSION_COOKIE_AGE is 90 days with SESSION_SAVE_EVERY_REQUEST, and that is the
right call for the audience: a 60-year-old member who opens the directory once a
month should not be logged out. Magic-link re-auth is an operator-mediated
WhatsApp DM, so an expired member session costs Bomino real work.

It is the wrong call for staff. A co-admin session can issue a login link for
ANY member (gestion/member_login_link), edit profiles, suspend accounts; the
super-admin session reaches /admin/. A stolen or borrowed laptop stays authorized
for a quarter.

So: members keep the long sliding session, staff get a short one, applied at
login via the user_logged_in signal.
"""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

#: 12 hours — a working day. Long enough that a co-admin doing a batch of
#: approvals is not re-authenticating constantly; short enough that a lost
#: device is not a standing grant.
STAFF_SESSION_AGE = 60 * 60 * 12


@receiver(user_logged_in)
def shorten_privileged_sessions(sender, request, user, **kwargs):
    """Downgrade the session lifetime for staff at login.

    Set on the session itself rather than globally, because SESSION_COOKIE_AGE
    is a single project-wide value and the two populations need different ones.
    """
    if not getattr(user, "is_staff", False):
        return  # ordinary member: keep the 90-day sliding session
    if request is None or not hasattr(request, "session"):
        return
    request.session.set_expiry(STAFF_SESSION_AGE)
