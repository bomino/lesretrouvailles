from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAdapter(DefaultAccountAdapter):
    """Direct self-signup is disabled. Members enter via cooptation (P3)."""

    def is_open_for_signup(self, request):
        return False
