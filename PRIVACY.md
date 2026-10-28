# Publication privacy checks

The initial public source was checked manually and scanned with Gitleaks before publication.

## What was checked

- Both automation sources and their local installation files were inspected for embedded keys, tokens, passwords, private account values, personal filesystem paths, and machine-specific identifiers.
- The publication contains only an explicit set of source files, tests, installation code, documentation, and the licence. Existing credentials, Codex configuration, account responses, logs, state, and compiled binaries were not copied into it.
- Personal paths and launch-service identifiers were replaced by an installer that generates configuration for the current user.
- The Codex helper uses executable discovery instead of assuming a particular Homebrew installation. It does not print raw app-server responses or error messages, which could contain private account details.
- Tests use invented examples. The publication scan found no embedded credentials. Git history was also checked before pushing.
- Git commits use a GitHub-provided no-reply address. The public repository owner's GitHub handle in the clone URL and commit attribution is intentional.

## Runtime data

The generated login configuration contains paths specific to the installing user and stays outside the checkout. Codex usage percentages, reset times, and alert history are local runtime data; do not upload them when reporting an issue. Notifications may show usage on the lock screen depending on macOS settings.

The lid helper has no networking code. The Codex helper invokes the user's own Codex CLI, whose existing sign-in, configuration, and communication with OpenAI remain its responsibility. Neither helper asks for credentials or includes an analytics or upload endpoint of its own.

## Recheck changes before sharing

Review the files and Git history you intend to publish. If Gitleaks is already installed, the checks used here can be repeated with:

```sh
gitleaks dir --redact .
gitleaks git --redact .
```

A clean scan reduces risk; it cannot prove that every possible private value has been found. The ignore rules and these checks must be repeated when adding more scripts or configuration.
