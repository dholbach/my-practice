from django.test import TestCase

from config.exception_reporter import PIIExceptionReporterFilter


class PIIExceptionReporterFilterTests(TestCase):
    def test_pii_fields_scrubbed(self):
        filter_instance = PIIExceptionReporterFilter()

        # Mock request & tb_frame if needed, but we can test hidden_settings regex
        regex = filter_instance.hidden_settings

        # Standard things
        self.assertTrue(regex.search("API_KEY"))
        self.assertTrue(regex.search("PASSWORD"))

        # PII things
        self.assertTrue(regex.search("email_address"))
        self.assertTrue(regex.search("client_name"))
        self.assertTrue(regex.search("first_name"))
        self.assertTrue(regex.search("last_name"))
        self.assertTrue(regex.search("phone_number"))
        self.assertTrue(regex.search("address"))
        self.assertTrue(regex.search("IBAN"))

        # Non-PII
        self.assertFalse(regex.search("amount"))
        self.assertFalse(regex.search("session_date"))

    def test_get_traceback_frame_variables_manual(self):
        filter_instance = PIIExceptionReporterFilter()

        # We simulate a frame dictionary context
        class DummyFrame:
            def __init__(self, locals_dict):
                self.f_locals = locals_dict
                self.f_code = type("DummyCode", (), {"co_name": "test", "co_flags": 0})()
                self.f_back = None  # Django 6+ traverses f_back; None terminates the loop

        locals_dict = {
            "email": "max@example.com",
            "client_name": "Max Mustermann",
            "session_duration": 60,
            "api_secret": "super_secret",
        }

        frame = DummyFrame(locals_dict)
        cleansed_items = filter_instance.get_traceback_frame_variables(None, frame)
        cleansed_dict = dict(cleansed_items)

        self.assertEqual(cleansed_dict["email"], filter_instance.cleansed_substitute)
        self.assertEqual(cleansed_dict["client_name"], filter_instance.cleansed_substitute)
        self.assertEqual(cleansed_dict["api_secret"], filter_instance.cleansed_substitute)
        self.assertEqual(cleansed_dict["session_duration"], 60)
