"""prod.py must not take a .env.example placeholder for a real secret.

A self-hoster who copies .env.example to .env instead of running `./prod.py setup`
has `DJANGO_SECRET_KEY=GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME`. `_read_env`
keeps inline comments (so `_write_env` can round-trip a file), which made that
value look set to setup and to the pre-flight check.
"""

import contextlib
import io

from django.test import SimpleTestCase

from .test_prod_network import ProdNetworkTestBase


class SecretUnsetTests(SimpleTestCase):
    def setUp(self):
        from .test_prod_network import _load_prod

        self.prod = _load_prod()

    def test_missing_and_empty_are_unset(self):
        self.assertTrue(self.prod._secret_unset({}, "FERNET_KEY"))
        self.assertTrue(self.prod._secret_unset({"FERNET_KEY": ""}, "FERNET_KEY"))

    def test_placeholder_from_the_example_is_unset(self):
        env = {"DJANGO_SECRET_KEY": "GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME"}
        self.assertTrue(self.prod._secret_unset(env, "DJANGO_SECRET_KEY"))

    def test_real_value_is_set(self):
        self.assertFalse(self.prod._secret_unset({"FERNET_KEY": "abc123="}, "FERNET_KEY"))


class RequireSecretsTests(ProdNetworkTestBase):
    def test_placeholders_are_reported_as_missing(self):
        self.env_file.write_text(
            "DJANGO_SECRET_KEY=GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME\n"
            "POSTGRES_PASSWORD=CHANGE_THIS_TO_A_STRONG_PASSWORD  # CHANGE ME\n"
            "FERNET_KEY=GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME\n"
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            self.prod._require_secrets()
        for key in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "FERNET_KEY"):
            self.assertIn(key, err.getvalue())

    def test_real_secrets_pass(self):
        self.env_file.write_text("DJANGO_SECRET_KEY=a\nPOSTGRES_PASSWORD=b\nFERNET_KEY=c\n")
        self.prod._require_secrets()
