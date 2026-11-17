"""prod.py must not take a .env.example placeholder for a real secret.

A self-hoster who copies .env.example to .env instead of running `./prod.py setup`
has `DJANGO_SECRET_KEY=GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME`. `_read_env`
keeps inline comments (so `_write_env` can round-trip a file), which made that
value look set to setup and to the pre-flight check.
"""

import contextlib
import io
from unittest import mock

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


class AddMissingKeysTests(SimpleTestCase):
    def setUp(self):
        from .test_prod_network import _load_prod

        self.prod = _load_prod()

    def generate(self, env):
        with (
            mock.patch.object(self.prod, "_generate_fernet_key", return_value="fernet-from-image"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            added = self.prod._add_missing_keys(env)
        return env, added

    def test_an_empty_env_gets_all_three(self):
        env, added = self.generate({})
        self.assertEqual(added, ["DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "FERNET_KEY"])
        self.assertEqual(env["FERNET_KEY"], "fernet-from-image")
        self.assertGreaterEqual(len(env["DJANGO_SECRET_KEY"]), 50)

    def test_existing_secrets_are_never_replaced(self):
        existing = {"DJANGO_SECRET_KEY": "a", "POSTGRES_PASSWORD": "b", "FERNET_KEY": "c"}
        env, added = self.generate(dict(existing))
        self.assertEqual(added, [])
        self.assertEqual(env, existing)

    def test_a_placeholder_is_replaced_and_a_real_value_kept(self):
        env, added = self.generate(
            {
                "DJANGO_SECRET_KEY": "GENERATE_A_KEY_AND_PUT_IT_HERE  # CHANGE ME",
                "POSTGRES_PASSWORD": "kept",
                "FERNET_KEY": "kept-too",
            }
        )
        self.assertEqual(added, ["DJANGO_SECRET_KEY"])
        self.assertEqual(env["POSTGRES_PASSWORD"], "kept")
        self.assertEqual(env["FERNET_KEY"], "kept-too")


class ManageInteractivelyTests(SimpleTestCase):
    def setUp(self):
        from .test_prod_network import _load_prod

        self.prod = _load_prod()

    def run_step(self, returncode):
        out = io.StringIO()
        with (
            mock.patch.object(
                self.prod, "manage", return_value=mock.Mock(returncode=returncode)
            ) as manage,
            contextlib.redirect_stdout(out),
        ):
            self.prod._manage_interactively(
                "Creating your login", "Prompts follow.", "createsuperuser"
            )
        return manage, out.getvalue()

    def test_success_prints_only_the_intro(self):
        manage, out = self.run_step(0)
        manage.assert_called_once_with("createsuperuser")
        self.assertIn("Prompts follow.", out)
        self.assertNotIn("did not complete", out)

    def test_failure_says_how_to_run_it_later_and_carries_on(self):
        _manage, out = self.run_step(1)
        self.assertIn("createsuperuser did not complete", out)
        self.assertIn("./prod.py manage createsuperuser", out)
