from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Registers the user_logged_in receiver that shortens staff sessions.
        # Lives in alumni/, but needs an AppConfig.ready to be imported — core
        # is the natural cross-cutting home (alumni is the project package and
        # has no AppConfig of its own beyond the admin site).
        from alumni import sessions  # noqa: F401
