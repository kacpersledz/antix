# Android Terminal acceptance test

After merging the V1 PR into `master`, on a fresh Android native Terminal Debian
VM as the normal user:

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

If bootstrap stops because `nix-users` membership is inactive, log out and back
in or restart the VM, then:

```sh
bash ~/.antix/bootstrap.sh
```

Until you publish Antix's own enrollment, credentials intentionally remain absent.
Complete the standalone trusted-machine enrollment in `docs/secrets.md` once
and publish the two repository artifacts. For an enrolled repository, paste the
Antix identity from Bitwarden only at the hidden prompt. Then:

```sh
antix-doctor
nix --version
antix-rebuild
bash ~/.antix/bootstrap.sh
ssh -T git@github.com
git -C ~/.antix remote -v
antix-codex
```

Confirm bootstrap/rebuild can rerun without damaging existing credentials or
mutable `~/.codex`. Close the Terminal UI while Codex is running, reopen it and
run `antix-codex` again; confirm it reattaches to the same process. VM reboot or
wipe necessarily ends that process.

Check `stat -c '%a' ~/.config/sops/age ~/.config/sops/age/keys.txt` reports 700 and
600. Check the resolved runtime SSH secret has mode 400. Do not print its contents.
Test `antix-update` on a clean `master`, then verify it refuses a dirty checkout
without losing local edits. Existing conflicting dotfiles must stop Home Manager
activation without overwriting them. Finally wipe/recreate the disposable VM
and repeat the one-command recovery to validate the published enrollment.

Before merge, test the PR branch explicitly rather than the `master` installer:
clone the PR branch over public HTTPS into `~/.antix` and run
`bash ~/.antix/bootstrap.sh`. `antix-update` intentionally refuses non-master
branches; switch to `master` after the PR is merged and your checkout is clean.
