"""Tests for the run_scheduled_jobs management command (consolidated hourly timer)."""

from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from ..management.commands.run_scheduled_jobs import JOBS


class RunScheduledJobsTest(SimpleTestCase):
    def _run(self):
        out, err = StringIO(), StringIO()
        call_command("run_scheduled_jobs", stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    @patch("my_practice.management.commands.run_scheduled_jobs.call_command")
    def test_runs_all_jobs_in_order(self, mock_call_command):
        out, _err = self._run()
        called_jobs = [call.args[0] for call in mock_call_command.call_args_list]
        self.assertEqual(called_jobs, JOBS)
        self.assertIn("All scheduled jobs completed.", out)

    @patch("my_practice.management.commands.run_scheduled_jobs.call_command")
    def test_one_failing_job_does_not_block_the_others(self, mock_call_command):
        def side_effect(job, **kwargs):
            if job == "update_client_tags":
                raise RuntimeError("boom")

        mock_call_command.side_effect = side_effect

        with self.assertRaises(CommandError) as ctx:
            self._run()

        called_jobs = [call.args[0] for call in mock_call_command.call_args_list]
        self.assertEqual(called_jobs, JOBS, "all jobs should still run despite one failing")
        self.assertIn("update_client_tags", str(ctx.exception))

    @patch("my_practice.management.commands.run_scheduled_jobs.call_command")
    def test_all_jobs_failing_are_all_reported(self, mock_call_command):
        mock_call_command.side_effect = RuntimeError("boom")

        with self.assertRaises(CommandError) as ctx:
            self._run()

        for job in JOBS:
            self.assertIn(job, str(ctx.exception))
