"""Tests for how `prod.py` decides where port 8000 is published (#511).

docker-compose.prod.yml used to publish the app on every interface. It now
defaults to loopback, so these cover the three places that matter: setup asks,
an existing installation keeps working after an update, and a reverse-proxy
setup that leaves the port open beside the proxy is called out.
"""

import contextlib
import importlib.util
import io
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from .test_release_guardrails import REPO_ROOT


def _load_prod():
    spec = importlib.util.spec_from_file_location("prod_under_test", REPO_ROOT / "prod.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProdNetworkTestBase(SimpleTestCase):
    def setUp(self):
        self.prod = _load_prod()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.env_file = Path(tmp.name) / ".env"
        self.prod.ENV_FILE = str(self.env_file)

    def run_quietly(self, func, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = func(*args)
        return result, out.getvalue()


class ComposeBindAddressTests(SimpleTestCase):
    def test_port_is_published_on_loopback_by_default(self):
        compose = (REPO_ROOT / "docker-compose.prod.yml").read_text()
        ports = re.findall(r'^\s+- "(.*:8000:8000)"', compose, re.M)
        self.assertEqual(ports, ["${MY_PRACTICE_BIND_ADDRESS:-127.0.0.1}:8000:8000"])

    def test_dev_stack_binds_loopback(self):
        # The dev stack runs with network_mode: host, so gunicorn's bind address
        # is the only thing keeping it off the LAN.
        compose = (REPO_ROOT / "docker-compose.yml").read_text()
        self.assertIn("network_mode: host", compose)
        self.assertEqual(re.findall(r"gunicorn --bind (\S+)", compose), ["127.0.0.1:8000"])

    def test_bind_address_documented_in_env_example(self):
        self.assertIn("MY_PRACTICE_BIND_ADDRESS=", (REPO_ROOT / ".env.example").read_text())


class EnsureBindAddressTests(ProdNetworkTestBase):
    def test_existing_installation_keeps_listening_on_every_interface(self):
        self.env_file.write_text("FERNET_KEY=abc")  # no trailing newline
        _, out = self.run_quietly(self.prod._ensure_bind_address)
        self.assertEqual(self.prod._read_env()["MY_PRACTICE_BIND_ADDRESS"], "0.0.0.0")
        self.assertEqual(self.prod._read_env()["FERNET_KEY"], "abc")
        self.assertIn("127.0.0.1", out)

    def test_explicit_choice_is_left_alone(self):
        self.env_file.write_text("MY_PRACTICE_BIND_ADDRESS=127.0.0.1\n")
        _, out = self.run_quietly(self.prod._ensure_bind_address)
        self.assertEqual(self.env_file.read_text(), "MY_PRACTICE_BIND_ADDRESS=127.0.0.1\n")
        self.assertEqual(out, "")


class ProxyBypassWarningTests(ProdNetworkTestBase):
    def warning(self, env):
        self.env_file.write_text(env)
        return self.run_quietly(self.prod._warn_if_proxy_bypassable)[1]

    def test_warns_when_https_is_trusted_and_port_is_open(self):
        out = self.warning("SECURE_SSL_REDIRECT=true\nMY_PRACTICE_BIND_ADDRESS=0.0.0.0\n")
        self.assertIn("claim HTTPS", out)

    def test_silent_behind_a_proxy_on_loopback(self):
        self.assertEqual(
            self.warning("SECURE_SSL_REDIRECT=true\nMY_PRACTICE_BIND_ADDRESS=127.0.0.1\n"), ""
        )
        self.assertEqual(self.warning("SECURE_SSL_REDIRECT=true\n"), "")

    def test_silent_for_plain_http_on_the_network(self):
        self.assertEqual(
            self.warning("SECURE_SSL_REDIRECT=false\nMY_PRACTICE_BIND_ADDRESS=0.0.0.0\n"), ""
        )


class AskAccessModeTests(ProdNetworkTestBase):
    def ask(self, answers, env=None):
        with mock.patch("builtins.input", side_effect=answers):
            (values, url), _ = self.run_quietly(self.prod._ask_access_mode, env or {})
        return values, url

    def test_this_machine_only_is_the_default(self):
        values, url = self.ask([""])
        self.assertEqual(values["MY_PRACTICE_BIND_ADDRESS"], "127.0.0.1")
        self.assertEqual(values["SECURE_SSL_REDIRECT"], "false")
        self.assertEqual(values["DJANGO_ALLOWED_HOSTS"], "localhost,127.0.0.1")
        self.assertEqual(url, "http://localhost:8000")

    def test_reverse_proxy_stays_on_loopback_and_trusts_https(self):
        values, url = self.ask(["2", "practice.example"])
        self.assertEqual(values["MY_PRACTICE_BIND_ADDRESS"], "127.0.0.1")
        self.assertEqual(values["SECURE_SSL_REDIRECT"], "true")
        self.assertEqual(values["DJANGO_ALLOWED_HOSTS"], "practice.example,localhost,127.0.0.1")
        self.assertEqual(url, "https://practice.example")

    def test_network_access_keeps_existing_hosts(self):
        values, url = self.ask(["3", "192.168.1.20"], {"DJANGO_ALLOWED_HOSTS": "nas.local"})
        self.assertEqual(values["MY_PRACTICE_BIND_ADDRESS"], "0.0.0.0")
        self.assertEqual(
            values["DJANGO_ALLOWED_HOSTS"], "192.168.1.20,nas.local,localhost,127.0.0.1"
        )
        self.assertEqual(url, "http://192.168.1.20:8000")

    def test_closed_stdin_means_this_machine_only(self):
        values, _ = self.ask(EOFError())
        self.assertEqual(values["MY_PRACTICE_BIND_ADDRESS"], "127.0.0.1")
