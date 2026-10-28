# Mute on lid close

Mutes your MacBook's current sound output when you close its lid. Opening the lid leaves the sound muted; the helper never restores the volume. You can unmute normally whenever you want.

The helper listens for macOS lid events rather than polling. It also checks the lid before sleep and when starting. It does not change sleep, display, or power settings.

## Requirements

- A MacBook running macOS 12 or newer. The code uses APIs available from macOS 12; testing has been on a newer macOS release, not every supported release or MacBook model.
- Python 3.9 or newer for installation.
- Apple's Command Line Tools or Xcode. If needed, run `xcode-select --install` and finish Apple's installation prompt before continuing.
- An audio output that supports macOS system mute. Some HDMI, USB, and external audio devices control their volume in hardware and do not support it.

## Install

Download or clone the repository as described in the [main README](../README.md), then run this from the repository's top-level folder:

```sh
python3 install.py mute-on-lid-close
```

The installer builds the helper on your Mac, prepares its login configuration, and starts it for your user. No administrator password or extra app is needed. It refuses to overwrite an existing installation.

To install the files without starting the helper in the current session:

```sh
python3 install.py mute-on-lid-close --no-start
```

The login configuration is still installed, so macOS may start it at your next login. Run `Disable.command` below if you want it to stay disabled. To start it now, run:

```sh
"$HOME/.local/share/automated-mac-scripts/mute-on-lid-close/Enable.command"
```

## Check it works

Read the current lid and mute state without changing anything:

```sh
"$HOME/.local/share/automated-mac-scripts/mute-on-lid-close/mute-on-lid-close" --status
```

With sound currently unmuted, close the lid, wait a few seconds, and reopen it. The sound should stay muted. This test is needed to check event timing on your particular Mac.

To inspect the helper's log:

```sh
tail -n 20 "$HOME/Library/Logs/automated-mac-scripts/mute-on-lid-close.log"
```

The log records readiness, lid events, and failures. It contains no account information or audio content.

## Disable or enable

Disable now and at future logins:

```sh
"$HOME/.local/share/automated-mac-scripts/mute-on-lid-close/Disable.command"
```

Enable again:

```sh
"$HOME/.local/share/automated-mac-scripts/mute-on-lid-close/Enable.command"
```

Disabling does not change the current mute state. Both control files can also be opened from Finder.

## Remove or update

Run `Disable.command` first. Then remove these two items using Finder (**Go → Go to Folder** supports pasting the paths):

- `~/.local/share/automated-mac-scripts/mute-on-lid-close`
- `~/Library/LaunchAgents/local.automated-mac-scripts.mute-on-lid-close.plist`

The log at `~/Library/Logs/automated-mac-scripts/mute-on-lid-close.log` can be kept for diagnosis or removed separately. To update, download the newer source and install again after removing the disabled installation. Nothing else on the Mac needs changing.

## Limits

This acts when the lid closes. If you manually unmute while the lid remains closed, it does not continuously force mute. Starting the helper with the lid already closed also mutes the output. On logout it stops; it starts again at your next login. No script runs while the Mac is shut down.

Only the current default audio output is muted. Switching to another output after closing the lid is not monitored. If a device does not support system mute, the helper reports an error and retries after a short delay; it cannot control a hardware volume knob.

If you previously installed another version of a lid helper, disable that copy separately to avoid two watchers. This installer uses its own names and will not modify unrelated automations.
