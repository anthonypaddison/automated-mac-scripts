import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "codex-usage-alert" / "codex_usage_alert.py"
spec = importlib.util.spec_from_file_location("usage", SCRIPT)
usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


class UsageTests(unittest.TestCase):
    def test_selects_weekly_window_from_named_bucket(self):
        response = {
            "rateLimitsByLimitId": {"codex": {
                "primary": {"usedPercent": 95, "windowDurationMins": 300},
                "secondary": {"usedPercent": 52, "windowDurationMins": 10080, "resetsAt": 2000000000},
            }},
            "rateLimits": {"primary": {"usedPercent": 3, "windowDurationMins": 10080}},
        }
        self.assertEqual(usage.weekly_usage(response), (52.0, 2000000000))

    def test_legacy_primary_weekly_window(self):
        self.assertEqual(usage.weekly_usage({"rateLimits": {
            "primary": {"usedPercent": 25, "windowDurationMins": 10080, "resetsAt": None},
        }}), (25.0, None))

    def test_missing_or_invalid_usage_does_not_disclose_response(self):
        for response in [
            {"accountId": "private-fixture-value", "rateLimits": {}},
            {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": None}}},
            {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": "nan"}}},
            {"rateLimits": {"primary": {"windowDurationMins": 10080, "usedPercent": -1}}},
        ]:
            with self.subTest(response=response):
                with self.assertRaises(usage.UsageError) as error:
                    usage.weekly_usage(response)
                self.assertNotIn("private-fixture-value", str(error.exception))

    def test_silent_and_partial_line_servers_respect_timeout(self):
        for code in ["import time; time.sleep(5)", "import sys,time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(5)"]:
            proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
            try:
                started = time.monotonic()
                with self.assertRaises(TimeoutError):
                    usage.read_response(proc, 7, timeout=0.1)
                self.assertLess(time.monotonic() - started, 2)
            finally:
                proc.terminate()
                proc.wait(timeout=2)
                proc.stdout.close()

    def test_notifications_and_fragmented_replies_do_not_hide_response(self):
        code = "import sys,time; print('{\"method\":\"notice\"}',flush=True); sys.stdout.write('{\"id\":7,'); sys.stdout.flush(); time.sleep(.02); print('\"result\":{\"ok\":true}}',flush=True)"
        with subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE) as proc:
            self.assertEqual(usage.read_response(proc, 7), {"ok": True})

    def test_protocol_errors_do_not_dump_server_messages(self):
        code = "print('{\"id\":7,\"error\":{\"message\":\"private-fixture-value\"}}',flush=True)"
        with subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE) as proc:
            with self.assertRaises(usage.UsageError) as error:
                usage.read_response(proc, 7)
        self.assertNotIn("private-fixture-value", str(error.exception))

    def test_check_mode_does_not_write_state_or_send_notifications(self):
        with patch.object(usage, "fetch_usage", return_value=(60.0, None)), \
             patch.object(usage, "save_state") as save, \
             patch.object(usage, "notify") as notify, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(usage.main(["--check"]), 0)
        save.assert_not_called()
        notify.assert_not_called()

    def test_thresholds_are_not_repeated_until_reset(self):
        state = {"reset_at": 1234, "notified_thresholds": [50, 60], "status_hour": "unused"}
        with patch.object(usage, "load_state", return_value=state), \
             patch.object(usage, "save_state") as save, \
             patch.object(usage, "notify") as notify:
            usage.alert(72.0, 1234, now=usage.datetime(2026, 1, 1, 12, 30))
            self.assertEqual(notify.call_count, 1)
            self.assertIn("70%", notify.call_args.args[1])
            self.assertEqual(save.call_args.args[0]["notified_thresholds"], [50, 60, 70])

    def test_new_reset_rearms_thresholds(self):
        with patch.object(usage, "load_state", return_value={"reset_at": 1, "notified_thresholds": [50]}), \
             patch.object(usage, "save_state"), patch.object(usage, "notify") as notify:
            usage.alert(55.0, 2, now=usage.datetime(2026, 1, 1, 12, 30))
            self.assertEqual(notify.call_count, 1)

    def test_state_file_is_private_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "private state" / "state.json"
            with patch.object(usage, "STATE_FILE", path):
                usage.save_state({"reset_at": 1234, "notified_thresholds": [50]})
                self.assertEqual(usage.load_state()["notified_thresholds"], [50])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(len(list(path.parent.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
