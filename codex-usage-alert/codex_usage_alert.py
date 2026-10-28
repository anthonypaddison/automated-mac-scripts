#!/usr/bin/env python3
"""Read Codex's weekly usage and send local macOS notifications."""

import argparse
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

WEEKLY_MINUTES = 7 * 24 * 60
THRESHOLDS = [50, 60, 70, 80, 90, 100]
STATE_FILE = Path.home() / "Library/Application Support/automated-mac-scripts/codex-usage-alert/state.json"


class UsageError(Exception):
    """An error safe to show without disclosing account or protocol details."""


def read_response(proc, request_id, timeout=10):
    """Bound the whole read, including silent servers and incomplete lines."""
    deadline = time.monotonic() + timeout
    buffer = b""
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError("Timed out waiting for Codex app-server.")
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                raise UsageError("Codex app-server closed before replying. Check your CLI version and sign-in.")
            buffer += chunk
            if len(buffer) > 1024 * 1024:
                raise UsageError("Codex app-server returned an oversized response.")
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(message, dict) or message.get("id") != request_id:
                    continue
                if "error" in message:
                    # Server errors can contain private account information.
                    raise UsageError("Codex could not read usage. Check your CLI version and ChatGPT sign-in.")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise UsageError("Codex returned an unsupported response format.")
                return result


def send(proc, message):
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def weekly_usage(response):
    buckets = response.get("rateLimitsByLimitId") or {}
    limits = buckets.get("codex") or response.get("rateLimits") or {}
    for window in (limits.get("primary"), limits.get("secondary")):
        if not window or window.get("windowDurationMins") != WEEKLY_MINUTES:
            continue
        try:
            used = float(window["usedPercent"])
        except (KeyError, TypeError, ValueError):
            raise UsageError("Codex did not provide a valid weekly usage percentage.") from None
        if not math.isfinite(used) or not 0 <= used <= 100:
            raise UsageError("Codex did not provide a valid weekly usage percentage.")
        reset = window.get("resetsAt")
        if reset is not None and (not isinstance(reset, (int, float)) or not math.isfinite(reset)):
            raise UsageError("Codex did not provide a valid reset time.")
        return used, reset
    raise UsageError("No seven-day usage window is available. Use a ChatGPT-signed-in Codex account with weekly limits.")


def fetch_usage(codex=None):
    executable = shutil.which(codex or "codex")
    if executable is None:
        raise UsageError("Codex CLI was not found. Install it, sign in, or pass --codex /path/to/codex.")
    # This starts no conversation or model turn and never reads auth files itself.
    proc = subprocess.Popen(
        [executable, "app-server", "--stdio"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        cwd=Path.home(),
    )
    try:
        send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "codex-usage-alert", "title": "Codex Usage Alert", "version": "1.2.0"},
            "capabilities": {"experimentalApi": True},
        }})
        read_response(proc, 1)
        send(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read", "params": None})
        return weekly_usage(read_response(proc, 2))
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        proc.stdin.close()
        proc.stdout.close()


def notify(title, message):
    subprocess.run([
        "/usr/bin/osascript", "-e", "on run argv",
        "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
        "-e", "end run", str(message), str(title),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)


def load_state():
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("notified_thresholds"), list):
            return {}
        state["notified_thresholds"] = [value for value in state["notified_thresholds"] if value in THRESHOLDS]
        return state
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE_FILE.parent.chmod(0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=STATE_FILE.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(state, file, indent=2)
            file.write("\n")
        temporary.replace(STATE_FILE)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def alert(used, resets_at, now=None):
    state = load_state()
    if state.get("reset_at") != resets_at:
        state = {}
    state.setdefault("reset_at", resets_at)
    notified = state.setdefault("notified_thresholds", [])
    now = now or datetime.now()
    status_hour = now.strftime("%Y-%m-%dT%H")
    remaining = 100 - used
    if now.minute < 5 and state.get("status_hour") != status_hour:
        notify("Codex Weekly Usage", f"{used:g}% used; {remaining:g}% remaining")
        state["status_hour"] = status_hour
    for threshold in THRESHOLDS:
        if used >= threshold and threshold not in notified:
            notify("Codex Usage Alert", f"Weekly usage has reached {threshold}%; currently {used:g}% used, {remaining:g}% remaining.")
            notified.append(threshold)
    save_state(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", help="Codex executable (otherwise resolved from PATH)")
    parser.add_argument("--check", action="store_true", help="Read usage without sending notifications or writing state")
    args = parser.parse_args(argv)
    try:
        used, resets_at = fetch_usage(args.codex)
        if not args.check:
            alert(used, resets_at)
        print(f"Codex weekly usage: {used:g}% used; {100 - used:g}% remaining")
        if resets_at is not None:
            print("Resets:", datetime.fromtimestamp(resets_at).strftime("%Y-%m-%d %H:%M:%S"))
        return 0
    except (UsageError, TimeoutError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except (OSError, ValueError, OverflowError, subprocess.SubprocessError):
        print("ERROR: Could not complete the usage check. Check local permissions, CLI sign-in, and notification settings.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
