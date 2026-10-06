# Antix

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

Antix restores a development environment in Android's native Linux Terminal,
which runs an aarch64 Debian VM under AVF. Treat that VM as disposable: the public
repository contains the reproducible configuration and encrypted credentials;
Bitwarden holds only Antix's private age identity.

V1 ships **unenrolled placeholders**. The command above installs the CLI
without GitHub credentials until you complete [initial enrollment](docs/secrets.md)
and publish the public recipient and encrypted SSH payload. Once enrolled,
recovery asks `Paste Antix AGE-SECRET-KEY from Bitwarden:` with hidden input.
Never reuse Wintix's identity or SSH key.

`install.sh` checks the platform, installs minimum HTTPS/Git dependencies and
clones `master` into `~/.antix`. Existing checkouts must be clean, on `master`,
and have the expected origin; updates are fast-forward only. It then hands off
to `bootstrap.sh`. Run as the normal Debian user with working `sudo`.

Bootstrap uses Debian's `nix-bin` and `nix-setup-systemd`, starts `nix-daemon`,
and enables `nix-command flakes`. Debian Nix 2.26.3 is the tested target version.
If it adds you to `nix-users` but your current session lacks that group, it stops
without claiming completion. Log out of the Debian session and back in, or
restart the VM, then resume:

```sh
bash ~/.antix/bootstrap.sh
```

Home Manager activates a standalone `aarch64-linux` environment. Existing
conflicting dotfiles cause activation to fail; preserve and review them manually
before retrying. No automatic backup overwrite is enabled. Home Manager
configures Zsh with the `clean` oh-my-zsh theme, Git plugin, completions,
autosuggestions and highlighting. Private/local additions remain possible in
`~/.config/zsh/local.zsh`. Bootstrap attempts to set Zsh as the login shell; the
change takes effect at the next login.

Packages include Git, curl, jq, ripgrep, fd, fzf, age, SOPS, OpenSSH, shpool,
Zsh, Codex and standard file/archiving tools. Stable nixpkgs and Home Manager
26.05 are pinned; Codex comes from a separately pinned unstable nixpkgs. Project
Node/JDK versions belong in individual project devShells.

| Command | Behavior |
| --- | --- |
| `antix-bootstrap` | Reconcile/recover the Debian and user environment |
| `antix-rebuild` | Apply current checkout without Git pulls or lock updates |
| `antix-update` | Fast-forward clean `master` from public HTTPS, then rebuild; no commits/pushes or flake updates |
| `antix-secrets-bootstrap` | Restore and validate Antix's age identity |
| `antix-secrets-enroll` | Deliberately enroll an SSH key; print its public key for manual registration |
| `antix-doctor` | Print pass/fail diagnostics; exit nonzero for incomplete setup |
| `antix-codex` | Create or reattach shpool session `antix-codex` running Codex |

Run `antix-codex` from the project directory for a new session. Reattaching keeps
the existing process and working directory. Detach with `Ctrl-Space Ctrl-q`; if
a stale connection prevents reattachment, run `shpool detach antix-codex`.
Shpool autostarts its daemon. It survives terminal UI disconnects while the VM
and daemon remain alive; it does not survive VM destruction or shutdown.

**All of `~/.codex` remains mutable**: configuration, AGENTS.md, agents,
authentication and session data are intentionally outside Home Manager in V1.
Authenticate Codex using its own interactive flow. Antix does not require
`gh auth login`.

Git initially uses public HTTPS. After decryption, bootstrap checks GitHub SSH
with the dedicated key and changes origin to SSH only on a successful greeting
for `kacpersledz`. On first connection, independently check GitHub's published
host fingerprint with interactive `ssh -T git@github.com`; bootstrap never
disables host verification. GitHub's successful authentication returns exit 1,
which Antix handles explicitly. Rerun bootstrap after registration/host trust.

The flake receives only the current user's name/home from `antix-rebuild` using
`--impure`; secrets are never read by Nix evaluation. sops-nix decrypts at runtime
with mode 0400 and skips its service if the age file is absent. An exact checked-in
placeholder disables secret declarations until enrollment; malformed enrolled
payloads are not treated as placeholders. Missing credentials show as failures
in doctor. The age identity uses `~/.config/sops/age/keys.txt` (0700 directory,
0600 file), independent of `XDG_CONFIG_HOME`.

Validation:

```sh
python3 -m unittest discover -s tests -v
for script in install.sh bootstrap.sh commands/*.sh; do bash -n "$script"; done
shellcheck -S error -e SC1090,SC1091 install.sh bootstrap.sh commands/*.sh
ANTIX_USER="$(id -un)" ANTIX_HOME="$HOME" nix eval --impure --no-update-lock-file --raw .#homeConfigurations.antix.activationPackage.drvPath
```

The lockfile reuses the verified input pins from Wintix, keeping only the four
Antix inputs. Script tests use fake tools and non-credential fixtures. Real Nix
activation, daemon/group/session behavior, shpool disconnect persistence and
runtime SOPS/GitHub authentication must be verified on Android. See
[the Android test procedure](docs/android-testing.md).
