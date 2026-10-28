# Codex usage alert

Checks the seven-day Codex usage window and sends local macOS notifications:

- A status notification near the start of each hour while the automation runs.
- Threshold alerts at 50%, 60%, 70%, 80%, 90%, and 100% used, once per threshold in each weekly window.

The installed automation checks every five minutes while you are logged in and the Mac is awake. It uses Codex's read-only `account/rateLimits/read` app-server method, without starting a model turn. [Official protocol documentation](https://learn.chatgpt.com/docs/app-server).

## Requirements

- macOS and Python 3.9 or newer.
- The [Codex CLI](https://developers.openai.com/codex/cli/) installed and available as `codex` in Terminal.
- Your own ChatGPT-signed-in Codex account with a seven-day usage window. API-key-only accounts or accounts without that window may not provide this data.

Check that the CLI works and sign in using Codex's normal interface if you have not already done so:

```sh
codex --version
codex login
```

The script does not need an API key, and you should not put one in this repository. Do not paste tokens or credentials into the script or its installer.

## Check without installing

From the repository's top-level folder:

```sh
python3 codex-usage-alert/codex_usage_alert.py --check
```

This prints usage and the reset time. It sends no notification and writes no alert state. The CLI still performs its normal authenticated request to OpenAI.

If Codex is not on your `PATH`, specify its executable:

```sh
python3 codex-usage-alert/codex_usage_alert.py --codex /path/to/codex --check
```

## Install

Download or clone the repository as described in the [main README](../README.md), then run this from the repository's top-level folder:

```sh
python3 install.py codex-usage-alert
```

Or use `python3 install.py codex-usage-alert --codex /path/to/codex` for a custom CLI location.

The installer records the Python and Codex locations on your own Mac, creates the five-minute login schedule, and runs an initial check. It requires no `sudo` and refuses to overwrite an existing installation. The first check may send several threshold notifications if your usage already exceeds several thresholds.

To install without launching an initial check in the current session, add `--no-start`. The login schedule is still installed and may run at your next login; run `Disable.command` below if you want it to stay disabled.

Allow notifications for Script Editor or the AppleScript notification sender shown by macOS if prompted. If checks appear in the log but no notification is visible, inspect **System Settings → Notifications**, Focus settings, and notification previews. macOS does not reliably display notifications while asleep or during every Focus mode.

## Disable or enable

Disable now and at future logins:

```sh
"$HOME/.local/share/automated-mac-scripts/codex-usage-alert/Disable.command"
```

Enable again:

```sh
"$HOME/.local/share/automated-mac-scripts/codex-usage-alert/Enable.command"
```

These files can also be opened from Finder. No credential files or Codex settings are changed by either command.

## Files and privacy

| Item | Location |
|---|---|
| Installed script and controls | `~/.local/share/automated-mac-scripts/codex-usage-alert` |
| Login schedule | `~/Library/LaunchAgents/local.automated-mac-scripts.codex-usage-alert.plist` |
| Usage/error log | `~/Library/Logs/automated-mac-scripts/codex-usage-alert.log` |
| Alert history | `~/Library/Application Support/automated-mac-scripts/codex-usage-alert/state.json` |

State is written with owner-only permissions. It contains the reset time, thresholds already notified, and the last hourly status identifier. The log shows percentages and reset times or generic errors; the script does not dump complete account responses or server error messages.

The helper itself has no networking code or credential handling. Your installed Codex CLI communicates with OpenAI using its own existing sign-in and configuration. Notifications can reveal usage on a lock screen, depending on your preview settings.

To read the log:

```sh
tail -n 20 "$HOME/Library/Logs/automated-mac-scripts/codex-usage-alert.log"
```

## Remove or update

Run `Disable.command` first. Then remove the installed script folder and the login-schedule file listed above using Finder. Keep the alert history when updating to avoid repeated threshold notifications; remove it separately only if you want to reset that history. The log can also be removed separately.

Download the newer repository source and run the installer again after removing the disabled installation. This does not affect your Codex installation, credentials, or other automations. If you previously installed a different usage-alert script, disable it separately to avoid duplicate notifications.

## Limits

This depends on Codex's app-server protocol and account-provided quota data, which may change. It reports the account's metered `codex` bucket, falling back to the legacy quota response; it is not a per-project or per-model usage report. If the seven-day window is missing, the script reports that instead of inventing a usage value. If the reset time is unavailable, it cannot reliably detect a new week to rearm thresholds.

Checks do not wake a sleeping Mac, and an hourly status is only sent if a check runs in the first five minutes of that hour. Alert suppression assumes you keep the state file and use one scheduled copy. Local logs are not automatically rotated; they may be removed while the helper is disabled.
