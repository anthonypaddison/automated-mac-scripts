# Automated Mac Scripts

Small macOS automations you can read, run, and change yourself. Free to use under the [MIT licence](LICENSE).

| Automation | What it does | Installation guide |
|---|---|---|
| Mute on lid close | Mutes the current sound output when a MacBook lid closes. Reopening the lid leaves it muted. | [Read the guide](mute-on-lid-close/README.md) |
| Codex usage alert | Checks weekly Codex usage every five minutes, with hourly status and threshold notifications. | [Read the guide](codex-usage-alert/README.md) |

## Get the scripts

Download this repository using GitHub's **Code → Download ZIP**, extract it, and open Terminal in the extracted folder. Alternatively:

```sh
git clone https://github.com/anthonypaddison/automated-mac-scripts.git
cd automated-mac-scripts
```

Choose the installation guide above. Each automation installs separately, runs as your normal user, and starts at login. No `sudo`, Python packages, or paid helper apps are needed. The installer requires Python 3.9 or newer; the lid helper also requires Apple's developer tools.

## Privacy

- The repository contains source code and synthetic tests. It contains no credentials, personal account data, generated machine-specific configuration, logs, state files, or compiled binaries.
- Installation generates paths for the current user. Nothing is hardcoded to the original author's Mac.
- The lid helper has no networking code. It reads the lid state and changes the default audio output's mute control.
- The Codex helper uses your own installed, signed-in Codex CLI to read usage from OpenAI. It does not read, copy, or export credentials itself, and it starts no model conversation. Codex's own configuration and network behaviour still apply.
- Codex notifications and local output show usage percentages and reset times. Its private local state records reset times and which alerts have been sent. These runtime files stay outside the repository.
- Notifications can appear on your lock screen depending on your macOS settings. Change notification previews if you prefer to hide usage there.

Do not commit generated configuration, account files, logs, or state when sharing your own changes. Common runtime and credential filenames are excluded by `.gitignore`; that is a guardrail, not a substitute for checking a diff.

## Testing

On macOS with Python 3.9+ and Apple's developer tools:

```sh
make test
make build
```

Tests cover quota parsing, alert suppression and reset, bounded protocol timeouts, private state storage, installer paths and overwrite protection, and lid-state transitions. They do not send real notifications, start login services, or change your sound. `make build` compiles the native helper into the ignored `.build` directory.

The original lid helper was tested by closing and reopening a MacBook lid. Hardware event timing and audio-device compatibility still need checking on your own Mac. These are community utilities with no affiliation with Apple or OpenAI.
