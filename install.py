#!/usr/bin/env python3
"""Install one automation for the current macOS user, without sudo."""

import argparse
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile

SOURCE_ROOT = Path(__file__).resolve().parent
SCRIPTS = {
    "mute-on-lid-close": ["mute-on-lid-close.c", "lid-state.h"],
    "codex-usage-alert": ["codex_usage_alert.py"],
}


def layout(name, user_home):
    label = f"local.automated-mac-scripts.{name}"
    return {
        "label": label,
        "app": user_home / ".local/share/automated-mac-scripts" / name,
        "plist": user_home / "Library/LaunchAgents" / f"{label}.plist",
        "log": user_home / "Library/Logs/automated-mac-scripts" / f"{name}.log",
    }


def make_plist(name, paths, python_bin, codex_bin=None):
    if name == "mute-on-lid-close":
        arguments = [str(paths["app"] / name)]
    else:
        arguments = [str(python_bin), str(paths["app"] / "codex_usage_alert.py"), "--codex", str(codex_bin)]
    result = {
        "Label": paths["label"],
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(paths["log"]),
        "StandardErrorPath": str(paths["log"]),
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"},
    }
    if name == "mute-on-lid-close":
        result.update(KeepAlive=True, ThrottleInterval=30)
    else:
        result["StartCalendarInterval"] = [{"Minute": minute} for minute in range(0, 60, 5)]
    return result


def control_script(paths, enable):
    lines = ["#!/bin/zsh", "set -eu", 'domain="gui/$(/usr/bin/id -u)"',
             f"label={shlex.quote(paths['label'])}", 'service="$domain/$label"']
    if enable:
        lines += ['/bin/launchctl enable "$service"',
                  'if ! /bin/launchctl print "$service" >/dev/null 2>&1; then',
                  f'    /bin/launchctl bootstrap "$domain" {shlex.quote(str(paths["plist"]))}',
                  "fi", "print 'Enabled now and at future logins.'"]
    else:
        lines += ['/bin/launchctl disable "$service"',
                  'if /bin/launchctl print "$service" >/dev/null 2>&1; then',
                  '    /bin/launchctl bootout "$service"', "fi",
                  "print 'Disabled now and at future logins. Current volume is unchanged.'"]
    return "\n".join(lines) + "\n"


def install_script(name, user_home, python_bin, codex_bin=None, start=True):
    paths = layout(name, user_home)
    for target in (paths["app"], paths["plist"]):
        if os.path.lexists(target):
            raise ValueError("Installation already exists. Disable and remove that installation before reinstalling; existing files were preserved.")
    if name == "codex-usage-alert":
        codex_bin = shutil.which(codex_bin or "codex")
        if codex_bin is None:
            raise ValueError("Codex CLI was not found. Install it first or pass --codex /path/to/codex.")
    elif shutil.which("clang") is None:
        raise ValueError("Apple developer tools are required. Run xcode-select --install first.")

    paths["app"].parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".install-", dir=paths["app"].parent) as temporary:
        staged = Path(temporary) / "payload"
        staged.mkdir(mode=0o700)
        for filename in SCRIPTS[name]:
            shutil.copyfile(SOURCE_ROOT / name / filename, staged / filename)
        if name == "mute-on-lid-close":
            subprocess.run([
                "clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                "-mmacosx-version-min=12.0", str(staged / "mute-on-lid-close.c"),
                "-framework", "CoreAudio", "-framework", "CoreFoundation", "-framework", "IOKit",
                "-o", str(staged / name),
            ], check=True)
        for enabled, filename in [(True, "Enable.command"), (False, "Disable.command")]:
            path = staged / filename
            path.write_text(control_script(paths, enabled), encoding="utf-8")
            path.chmod(0o700)

        paths["plist"].parent.mkdir(parents=True, exist_ok=True)
        paths["log"].parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Exclusive creation refuses to overwrite even if another installer races us.
        with paths["plist"].open("xb") as file:
            plistlib.dump(make_plist(name, paths, python_bin, codex_bin), file)
        paths["plist"].chmod(0o600)
        staged.rename(paths["app"])

    if start:
        subprocess.run(["/bin/zsh", str(paths["app"] / "Enable.command")], check=True)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", choices=SCRIPTS)
    parser.add_argument("--codex", help="Codex executable for the usage-alert script")
    parser.add_argument("--no-start", action="store_true", help="Install files without launching now; the login schedule is still installed")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("These automations require macOS.")
    if os.geteuid() == 0:
        parser.error("Run as your normal user; do not use sudo.")
    if args.codex and args.script != "codex-usage-alert":
        parser.error("--codex applies only to codex-usage-alert.")
    try:
        paths = install_script(args.script, Path.home(), Path(sys.executable).absolute(), args.codex, not args.no_start)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Installation did not finish: {error}", file=sys.stderr)
        print("Existing installations were not replaced. If files were prepared, use their Enable.command to retry startup.", file=sys.stderr)
        return 1
    print("Installed files:", paths["app"])
    print("Login configuration:", paths["plist"])
    if args.no_start:
        print("Not started now. The login schedule is installed; run Disable.command to keep it disabled at future logins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
