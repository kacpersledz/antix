# Antix

Antix is an **experimental minimal Android Nix/Home Manager baseline** for the
native Android Terminal aarch64 Debian VM. The full V1 realization attempted
heavy local builds, including `sops-install-secrets-0.0.1-go-modules`, and made
the VM effectively unusable. This experiment asks whether Debian Nix and a very
small Home Manager environment can install reliably on a fresh VM.

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

Run as the normal Debian user with working `sudo`. The installer uses HTTPS,
checks the platform, and clones clean `master` into `~/.antix`. Bootstrap installs
Debian `nix-bin` and `nix-setup-systemd`, enables the daemon, and adds the user to
`nix-users`. If group membership is not active, it stops cleanly. Restart the
session or VM, then resume:

```sh
bash ~/.antix/bootstrap.sh
```

The baseline retains standalone Home Manager activation, generic Linux support,
Debian's `/usr/share/doc/nix-bin/examples/nix.sh` profile hook (`nix.package = null`),
and the non-secret `ANTIX_USER` / `ANTIX_HOME` runtime identity parameters.
It installs Git with author `kacpersledz` / `casper.sledx@gmail.com`, and Zsh with
completion, autosuggestions, syntax highlighting, oh-my-zsh's `clean` theme and
`git` plugin. Optional `~/.config/zsh/local.zsh` extensions remain supported.
Bootstrap attempts to set `~/.nix-profile/bin/zsh` as the login shell. Existing
conflicting dotfiles stop activation for manual review.

Temporarily absent from automatic installation: **Codex, shpool, GitHub SSH
recovery, sops-nix, and the developer CLI bundle** (including age/SOPS/OpenSSH,
ripgrep/fd/fzf and convenience tools). There is no Bitwarden prompt, decryption,
SSH authentication attempt, or remote switching. Fresh checkouts retain
`https://github.com/kacpersledz/antix.git`.

The encrypted enrollment material `.sops.yaml` and
`secrets/github-ssh-key.yaml` remains preserved and untouched. Private Age keys
remain outside Git. Standalone enrollment/recovery scripts and their safety
tests are retained for later work; bootstrap does not invoke them.
[Enrollment documentation](docs/secrets.md) describes that inactive workflow.

Only stable nixpkgs and Home Manager are flake inputs. Home Manager follows
nixpkgs, pinned to the known 26.05 release-pipeline revision
`7fc6f2c20af09cdcaf48b92ec3121860139ec668` to remove cache freshness as a variable.
The HM CLI and all Antix package wrappers are disabled. Nonessential Home
Manager defaults for GPU integration, desktop MIME tools, manuals and service
switching are also disabled to keep the terminal baseline small. Invoke operations from
the checkout:

```sh
bash ~/.antix/commands/antix-rebuild.sh
bash ~/.antix/commands/antix-update.sh
```

Rebuild directly executes the activation package without updating the lock.
Update requires clean `master`, fetches public HTTPS and fast-forwards before
rebuilding; `--checkout-only` skips activation.

`~/.config/nix/nix.conf` includes `antix.conf`. Antix manages that separate file
with these conservative settings, also used by ARM64 CI:

```conf
experimental-features = nix-command flakes
max-jobs = 1
cores = 1
max-substitution-jobs = 2
http-connections = 4
```

Bootstrap refuses symlinked configs and unexpected managed content, permits
migration from the previous one-line config, and preserves user config entries.
Unexpected local builds cannot use all VM CPUs.

Validation:

```sh
python3 -m unittest discover -s tests -v
shellcheck -e SC1090,SC1091 install.sh bootstrap.sh commands/*.sh
git diff --check
nix eval --json --file tests/configuration.nix
export ANTIX_USER="$(id -un)" ANTIX_HOME="$HOME"
nix eval --impure --no-update-lock-file --raw .#homeConfigurations.antix.activationPackage.drvPath
nix flake check --no-build --no-update-lock-file
nix build --impure --no-update-lock-file --dry-run .#homeConfigurations.antix.activationPackage
nix build --impure --no-update-lock-file --no-link .#homeConfigurations.antix.activationPackage
```

ARM64 CI installs Debian Nix and performs evaluation, dry-run and real activation
package build, retaining logs. Inspect the local-build section: tiny generated
HM/config derivations are acceptable; Rust/Cargo, Go or `*-go-modules`, clang,
cmake, Codex or sops-install-secrets source builds require investigation.
A passing ARM64 build is required before considering the PR ready.
See [Android acceptance testing](docs/android-testing.md) for the fresh VM test.

Features will return incrementally only after this baseline is validated:
baseline → small CLI tools → ripgrep/fd/fzf → age/sops/openssh → Antix-native
secret decryption → shpool → lightweight Codex installation.
