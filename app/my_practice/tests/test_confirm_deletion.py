"""The shared "type yes" prompt of the commands that delete rows."""

from io import StringIO
from unittest import mock

from django.core.management.base import OutputWrapper
from django.core.management.color import no_style
from django.test import SimpleTestCase

from ..management.commands._confirm import confirm_deletion


class FakeCommand:
    def __init__(self):
        self.out = StringIO()
        self.stdout = OutputWrapper(self.out)
        self.style = no_style()


class ConfirmDeletionTests(SimpleTestCase):
    def ask(self, answer=None, *, tty=True, skip=False):
        command = FakeCommand()
        with (
            mock.patch("sys.stdin.isatty", return_value=tty),
            mock.patch("builtins.input", return_value=answer) as prompt,
        ):
            confirmed = confirm_deletion(command, "Delete 3? ", skip)
        return confirmed, command.out.getvalue(), prompt

    def test_yes_flag_skips_the_prompt(self):
        confirmed, out, prompt = self.ask(skip=True, tty=False)
        self.assertTrue(confirmed)
        prompt.assert_not_called()
        self.assertEqual(out, "")

    def test_typing_yes_confirms_in_any_case(self):
        for answer in ["yes", "YES", "Yes"]:
            with self.subTest(answer=answer):
                confirmed, _out, prompt = self.ask(answer)
                self.assertTrue(confirmed)
                prompt.assert_called_once_with("Delete 3? ")

    def test_anything_else_aborts(self):
        for answer in ["", "y", "no", "yes please"]:
            with self.subTest(answer=answer):
                confirmed, out, _prompt = self.ask(answer)
                self.assertFalse(confirmed)
                self.assertIn("Aborted", out)

    def test_without_a_terminal_it_aborts_and_points_to_yes(self):
        confirmed, out, prompt = self.ask("yes", tty=False)
        self.assertFalse(confirmed)
        prompt.assert_not_called()
        self.assertIn("Use --yes", out)
