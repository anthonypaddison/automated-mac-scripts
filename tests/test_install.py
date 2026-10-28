import importlib.util
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_paths_and_xml_work_for_another_user_with_spaces_and_symbols(self):
        user_home = Path("/Users/sample user & $value")
        paths = installer.layout("codex-usage-alert", user_home)
        config = installer.make_plist("codex-usage-alert", paths, "/python bin/python3", "/codex bin/codex")
        decoded = plistlib.loads(plistlib.dumps(config))
        self.assertEqual(decoded["ProgramArguments"], [
            "/python bin/python3", str(user_home / ".local/share/automated-mac-scripts/codex-usage-alert/codex_usage_alert.py"),
            "--codex", "/codex bin/codex",
        ])
        self.assertEqual(decoded["StartCalendarInterval"], [{"Minute": minute} for minute in range(0, 60, 5)])
        self.assertNotIn("KeepAlive", decoded)

    def test_mute_helper_restarts_and_runs_at_login(self):
        paths = installer.layout("mute-on-lid-close", Path("/Users/sample"))
        config = installer.make_plist("mute-on-lid-close", paths, "/python3")
        self.assertTrue(config["KeepAlive"])
        self.assertTrue(config["RunAtLoad"])
        self.assertEqual(config["ThrottleInterval"], 30)
        self.assertNotIn("StartCalendarInterval", config)

    def test_no_start_installs_into_temporary_home_without_running_launchctl(self):
        with tempfile.TemporaryDirectory(prefix="mac scripts & ") as directory:
            with patch.object(installer.subprocess, "run") as run:
                paths = installer.install_script("codex-usage-alert", Path(directory), Path(sys.executable), sys.executable, start=False)
                run.assert_not_called()
            self.assertTrue((paths["app"] / "codex_usage_alert.py").is_file())
            self.assertEqual(paths["plist"].stat().st_mode & 0o777, 0o600)
            config = plistlib.loads(paths["plist"].read_bytes())
            self.assertTrue(config["ProgramArguments"][1].startswith(directory))
            for filename in ("Enable.command", "Disable.command"):
                subprocess.run(["/bin/zsh", "-n", str(paths["app"] / filename)], check=True)

    def test_existing_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = installer.layout("codex-usage-alert", Path(directory))
            paths["app"].mkdir(parents=True)
            sentinel = paths["app"] / "keep.txt"
            sentinel.write_text("preserve")
            with self.assertRaises(ValueError):
                installer.install_script("codex-usage-alert", Path(directory), Path(sys.executable), sys.executable, start=False)
            self.assertEqual(sentinel.read_text(), "preserve")
            self.assertFalse(paths["plist"].exists())

    def test_broken_symlinks_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = installer.layout("mute-on-lid-close", Path(directory))
            paths["app"].parent.mkdir(parents=True)
            paths["app"].symlink_to(Path(directory) / "missing")
            with self.assertRaises(ValueError):
                installer.install_script("mute-on-lid-close", Path(directory), Path(sys.executable), start=False)
            self.assertTrue(paths["app"].is_symlink())


if __name__ == "__main__":
    unittest.main()
