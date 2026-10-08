# Antix

Antix Stage A restores the useful V1 development baseline for a fresh native
Android 17 Terminal Debian ARM64 VM. It uses Debian's Nix daemon and standalone
Home Manager with stable, pinned nixpkgs. Android runtime acceptance remains a
separate fresh-VM test; CI alone does not establish compatibility.

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

Run as the normal Debian user with working `sudo`. The installer uses HTTPS,
checks the platform, and clones clean `master` into `~/.antix`. Bootstrap installs
Debian `nix-bin` and `nix-setup-systemd`, enables the daemon, and adds the user to
`nix-users`. If the freshly added `nix-users` membership is not active in the current
login, bootstrap runs the Home Manager rebuild through `sg nix-users` as the
same unprivileged user. **No VM restart is required for installation.** Opening a fresh Android Terminal session after installation automatically enters Home Manager Zsh via an idempotent Bash startup hook (even if Android launches Bash directly).

The baseline retains standalone Home Manager activation, generic Linux support,
Debian's `/usr/share/doc/nix-bin/examples/nix.sh` profile hook (`nix.package = null`),
and the non-secret `ANTIX_USER` / `ANTIX_HOME` runtime identity parameters.
It installs git, curl, jq, ripgrep, fd, fzf, zsh, less, unzip, zip, tree, file
and which from stable nixpkgs. Git uses author `kacpersledz` / `casper.sledx@gmail.com`, and Zsh with
completion, autosuggestions, syntax highlighting, oh-my-zsh's `clean` theme and
`git` plugin. Optional `~/.config/zsh/local.zsh` extensions remain supported.
Bootstrap attempts to set `~/.nix-profile/bin/zsh` as the login shell. Home Manager manages Zsh's `.zshenv` so the
profile bin directory is available even when Android launches Zsh directly.
Bootstrap preserves existing Bash startup files and appends a marked hook to the active login file and ~/.bashrc. The hook only switches interactive terminal sessions; scripts remain Bash. Set `ANTIX_KEEP_BASH=1` before starting Bash to opt out. Symlinked or non-regular Bash startup files are refused for manual review. `~/.codex` remains unmanaged.
Node and JDK belong in project environments.

Deliberately deferred: **Age, SOPS, OpenSSH, GitHub SSH recovery, sops-nix,
Codex and shpool**. There is no Bitwarden prompt, decryption, SSH authentication
attempt, or remote switching. Fresh checkouts retain HTTPS remotes.

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
```

Bootstrap refuses symlinked configs and unexpected managed content, permits
migration from V1’s one-line config and the minimal baseline’s five-line config, and preserves user config entries.
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

Acceptance stages are independent: **A** restored baseline (this PR), **B**
Age/SOPS/OpenSSH and direct SSH recovery, **C** shpool disconnect/reattach tests,
**D** Codex with separate ARM64 cache/closure/build review. The retained
`antix-codex` script is inactive until C/D; command wrappers export no packages.

No bootstrap operation deletes store objects, runs garbage collection, wipes
profiles, or repairs corruption. Zero-byte store files require diagnosis or a
fresh VM, not dotfile-conflict handling.
