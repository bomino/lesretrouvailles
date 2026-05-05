from django.apps import AppConfig


class MemoriamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "memoriam"
    verbose_name = "In Memoriam"

    def ready(self) -> None:
        # Import signal handlers so they register at app load.
        # noqa: F401 — side-effect import.
        from . import signals  # noqa: F401
