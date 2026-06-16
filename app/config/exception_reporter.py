import re
from django.views.debug import SafeExceptionReporterFilter
from django.conf import settings


class PIIExceptionReporterFilter(SafeExceptionReporterFilter):
    """
    Extends Django's default filter to scrub PII (names, emails) globally
    from 500 error reports and tracebacks.
    Protects settings, POST parameters, and local variables on crash.
    """

    @property
    def hidden_settings(self):  # type: ignore[override]
        """
        Combines Django's default pattern (passwords/secrets)
        with our PII field names.
        """
        # Default: 'API|TOKEN|KEY|SECRET|PASS|SIGNATURE' (fallback)
        base_pattern = getattr(
            settings, "HIDDEN_SETTINGS", "API|TOKEN|KEY|SECRET|PASS|SIGNATURE|BEARER"
        )

        # PII field names to redact
        pii_pattern = "EMAIL|NAME|FIRST_NAME|LAST_NAME|FULL_NAME|CLIENT_NAME|PHONE|ADDRESS|IBAN|BIC|PHONE_NUMBER|MOBILE|SUBJECT_DE|SUBJECT_EN|CONTACT"

        combined_pattern = f"({base_pattern}|{pii_pattern})"

        return re.compile(combined_pattern, flags=re.IGNORECASE)

    def get_traceback_frame_variables(self, request, tb_frame):
        """
        Override to scrub all PII variables from the local scope of each
        traceback frame, in addition to @sensitive_variables() decorators.
        """
        # Run the standard Django filter first
        cleansed_items = super().get_traceback_frame_variables(request, tb_frame)

        cleansed_dict = {}
        for name, value in cleansed_items:
            # Skip variables already redacted by Django (self.cleansed_substitute = '**********')
            if value == self.cleansed_substitute:
                cleansed_dict[name] = value
                continue

            if bool(self.hidden_settings.search(str(name))):
                cleansed_dict[name] = self.cleansed_substitute
            else:
                cleansed_dict[name] = value

        return cleansed_dict.items()
