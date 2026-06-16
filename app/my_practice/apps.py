from django.apps import AppConfig


class PaymentsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "my_practice"
    verbose_name = "Therapy Payments & Invoicing"

    def ready(self):
        """Import signals when the app is ready."""
        import my_practice.signals  # noqa: F401
