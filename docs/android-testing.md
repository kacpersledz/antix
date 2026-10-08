# Stage A Android 17 Terminal acceptance test

This is the restored baseline; test only on a fresh native Debian ARM64 VM.
Before publishing a new baseline,
testing the PR branch directly on Android is preferred. After merge, use the
normal `master` installer for fresh-device acceptance testing. Updates
intentionally require clean `master`.

Published fresh VM test (normal user in native Android Terminal Debian):

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

Expected first run:
- Install Debian Nix packages if needed.
- Configure/start nix-daemon.
- Add droid to nix-users.
- Use `sg nix-users` automatically if the current login has stale group membership.

After installation, open a fresh Android Terminal session: it should enter Zsh automatically, even when Android launches Bash directly. No manual VM restart or second bootstrap run is required for `nix-users`.
Re-running `bash ~/.antix/bootstrap.sh` remains supported as an idempotency test.

Expected:
- NO Bitwarden prompt.
- NO secret recovery.
- NO Codex.
- NO shpool.
- NO large Rust/Go/compiler source build.
- Home Manager activation succeeds.
- Android Terminal remains responsive.
- Zsh is installed/usable.
- Git identity is correct.

Verification (use a new login for the shell/profile change):

```sh
which nix
nix --version
command -v zsh
zsh --version
git config --global user.name
git config --global user.email
git -C ~/.antix remote get-url origin
du -sh /nix/store
```

Expected Git identity: `kacpersledz` / `casper.sledx@gmail.com`.
Expected Git remote:

```text
https://github.com/kacpersledz/antix.git
```

Nix should be Debian's `/usr/bin/nix`; Zsh should be
`~/.nix-profile/bin/zsh`. `which` is included in the stable CLI bundle.
Record store size, install duration and responsiveness. Rerun bootstrap and
`bash ~/.antix/commands/antix-rebuild.sh` to verify idempotency. Confirm unmanaged
Nix config entries survive and conflicting dotfiles stop activation without
being overwritten. On clean master, test update, then confirm it refuses a dirty
checkout without losing edits.

Inspect ARM64 CI dry-run/build logs before declaring readiness: only tiny
generated local derivations are acceptable, with no heavyweight toolchain source
builds. CI success does not replace this fresh-device responsiveness test.
Encrypted enrollment files remain preserved; these features will be reintroduced
incrementally after the baseline passes.

Before merge, test the feature branch on a fresh VM with:

```sh
git clone --branch fix/zsh-store-integrity https://github.com/kacpersledz/antix.git ~/.antix
bash ~/.antix/bootstrap.sh
# After successful activation, close the session and open a fresh Debian login.
command -v zsh
zsh --version
for tool in git curl jq rg fd fzf zsh less unzip zip tree file which; do command -v "$tool" || break; done
bash ~/.antix/commands/antix-doctor.sh
bash ~/.antix/bootstrap.sh
bash ~/.antix/commands/antix-rebuild.sh
```

Zsh must resolve through the Home Manager profile with a clean login PATH. Bootstrap appends a guarded startup hook to the active Bash login file and ~/.bashrc, preserving existing content. Interactive Bash switches to Zsh; noninteractive scripts are unchanged. Test opt-out with `ANTIX_KEEP_BASH=1 bash -i` and verify the installer is idempotent.
If Android resumes an existing shell instead of starting a login, close/reopen
that session or run `exec ~/.nix-profile/bin/zsh -l`; changing `/etc/passwd`
alone does not initialize PATH. Existing Bash login content is preserved. If login-shell switching fails, source
`/usr/share/doc/nix-bin/examples/nix.sh` in the current Bash session and start
`~/.nix-profile/bin/zsh -l`. Review Zsh conflicts manually rather than deleting
them automatically.
Feature-branch update intentionally refuses operation; use rebuild there.

Record actual CI local derivations, closure size, activation duration, VM
responsiveness, and repeated-run results. No ARM64 build or Android compatibility
claim should be made until those respective checks run successfully.

## Debian Nix package setup warning

On a fresh Android Terminal Debian VM, `nix-setup-systemd` may print
`Could not execute systemctl` or `Job failed` while APT configures packages.
These messages do not, by themselves, establish that the socket remains down.
Bootstrap reloads systemd and disables independent nix-daemon.service
autostart. If the daemon is already active while the socket is inactive (the
observed fresh-VM race), bootstrap stops the daemon before enabling the socket.
A healthy active socket is left running. If socket startup still fails, bootstrap
retries after clearing the conflicting daemon state, reports systemd diagnostics,
and stops before Home Manager activation. A successful socket state is followed
by a real Nix daemon connection check.

On a fresh VM, the expected result is an active nix-daemon.socket; the daemon
service may become active again on demand after the connection check. Re-running
bootstrap must not stop the daemon when the socket is already healthy. Do not
wipe the Nix store because of the APT warning alone.

Fresh installs use `sg nix-users` for the rebuild while the login group is
stale; no VM restart is necessary to complete Stage A.

## Zsh integrity and recovery

A successful install now requires nonempty, hash-verified Home Manager-generated
`.zshrc` and `.zshenv`, matching activated symlinks and an isolated interactive
startup with Oh My Zsh's `clean` theme and `git` plugin. `programs.zsh.dotDir`
is explicitly the configured home. Nix evaluation is not a substitute for these
checks; noninteractive `zsh -lc` does not read `.zshrc`.

On a generated-artifact failure, rebuild attempts one pinned activation-package
`nix build --repair`, rechecks its outputs and activates the repaired generation.
Nix 2.26's repair mode hashes the closure and redownloads/rebuilds corrupt or
missing paths. An ordinary rebuild can reuse a corrupt registered output.
There are no manual store writes, deletion, garbage collection or rebuild loops.
Repair may require daemon authorization or available substitutes/build inputs;
failure is reported and stops installation. If verification still fails, preserve
the diagnostics: the underlying Nix store/runtime remains unreliable.

Confirmed facts from the reported VM: `.zshrc` was zero bytes and failed Nix
hash verification while evaluation was correct. Inspection found no repository
writer to these store files; Bash hooks refuse symlinks. Android filesystem or
Nix write failures remain hypotheses, not a demonstrated root cause. This patch
detects and attempts recovery; it does not prevent underlying corruption.

Copy-paste acceptance on a **fresh Android 17 native Debian ARM64 VM**, normal user:

```sh
set -e
git clone --branch fix/zsh-store-integrity https://github.com/kacpersledz/antix.git ~/.antix
bash ~/.antix/bootstrap.sh
# Must print PASS interactive Zsh and verified integrity, with no secret prompts.
for name in .zshrc .zshenv; do
  test -L "$HOME/$name"
  target=$(readlink -f "$HOME/$name")
  test -s "$target"
  nix-store --verify-path "$target"
done
grep -E 'plugins=|ZSH_THEME=|oh-my-zsh.sh' ~/.zshrc
env -i HOME="$HOME" USER="$(id -un)" PATH=/usr/bin:/bin TERM="${TERM:-dumb}" \
  "$HOME/.nix-profile/bin/zsh" -ic '
    [[ $ZSH_THEME == clean && ${plugins[(Ie)git]} -gt 0 ]] || exit 1
    (( $+functions[omz] && $+functions[git_prompt_info] )) || exit 1
    print "PASS clean/git/omz"
  '
bash ~/.antix/commands/antix-doctor.sh
bash ~/.antix/bootstrap.sh
bash ~/.antix/commands/antix-rebuild.sh
bash -c 'printf "PASS noninteractive Bash\n"'
"$HOME/.nix-profile/bin/zsh" -c '(( $+functions[omz] == 0 )) && print "PASS noninteractive Zsh"'
# Open a fresh Android Terminal session; expect Zsh and the clean prompt.
```

If doctor reports corruption, capture the resolved paths, byte sizes and
`nix-store --verify-path` errors, then run the rebuild command above. Do not edit
store files or deliberately corrupt the runner/VM to test repair. Regression
tests mock Nix with temporary fixtures; ARM64 CI checks real generated outputs
and interactive startup. Neither establishes Android runtime acceptance until
this checklist passes on the fresh device.
