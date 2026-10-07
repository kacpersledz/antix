# Minimal Android Terminal acceptance test

This is an experimental minimal baseline. Before publishing a new baseline,
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
- Stop cleanly if new group membership requires session/VM restart.

After restart:

```sh
bash ~/.antix/bootstrap.sh
```

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
which zsh
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
`~/.nix-profile/bin/zsh`. `which` is a host verification tool, not an HM package.
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
