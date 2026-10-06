# Antix secrets and recovery

Antix has its own age identity and Ed25519 GitHub SSH key. Bitwarden contains
only the `AGE-SECRET-KEY`; Git contains the public age recipient and SOPS-encrypted
SSH key. Never commit a plaintext private key or put it in Nix expressions.
No actual identity or SSH key is included in V1.

## First enrollment (one time, performed by you)

1. Bootstrap the unenrolled CLI environment first. If group membership requires
   a new session, resume with `bash ~/.antix/bootstrap.sh`.
2. Create a dedicated age identity outside the repository, with protected modes:

   ```sh
   umask 077
   mkdir -p ~/.config/sops/age
   chmod 700 ~/.config/sops/age
   # Only when keys.txt does not exist: age-keygen refuses to overwrite it.
   age-keygen -o ~/.config/sops/age/keys.txt
   age-keygen -y ~/.config/sops/age/keys.txt
   ```

   If that location already has Wintix/other material, stop and resolve ownership
   manually; never overwrite it. Save the Antix private identity in Bitwarden
   through your own secure UI. Do not paste it into chat or shell command arguments.
3. Replace `ANTIX_AGE_RECIPIENT_ENROLLMENT_REQUIRED` in `~/.antix/.sops.yaml`
   with only the derived public `age1...` recipient. Keep one exact `age:` line.
4. Run:

   ```sh
   antix-secrets-bootstrap
   antix-secrets-enroll
   ```

   The helper creates `~/.ssh/antix_github_ed25519`, encrypts into a protected
   temporary file next to the repository payload, decrypts it outside the
   repository, validates the OpenSSH private key and compares exact content.
   Only after all checks pass does it atomically replace the enrollment placeholder.
   Temporary plaintext is removed on exit; interrupted enrollment may leave a
   newly generated SSH pair, which requires deliberate reuse on retry.
5. Register only the printed SSH public key in GitHub manually. Antix never
   uploads or registers a key for you.
6. Review and commit **only** `.sops.yaml` and `secrets/github-ssh-key.yaml`,
   publishing them to `master` through your normal review flow. Do not alter
   `secrets/enrollment-placeholder.txt`, which defines the exact unenrolled sentinel.
7. Apply and verify:

   ```sh
   antix-rebuild
   systemctl --user restart sops-nix
   ssh -T git@github.com
   antix-bootstrap
   antix-doctor
   ```

   Verify GitHub's host fingerprint independently on first connection. A successful
   GitHub greeting with exit status 1 is normal. Bootstrap switches origin to SSH
   only once the greeting confirms the expected account.

## Disposable VM recovery

Run the README's single pasted command. At the hidden terminal prompt paste the
Antix identity from Bitwarden. Input is read from `/dev/tty`, so a piped installer
cannot consume the credential as script input. Validation and exact recipient
matching happen before atomic installation. Existing malformed, mismatched or
symlinked material is refused; an already correct identity succeeds idempotently.
The scripts disable tracing and never export or pass private identity text in
arguments. No Bitwarden or GitHub API token is needed.

`antix-secrets-bootstrap` restores only the identity. After a standalone restore,
run `antix-rebuild` if needed and `systemctl --user restart sops-nix` to decrypt.
The sops-nix secret lives under `~/.config/sops-nix/secrets/antix-github-ssh`, backed
by the user runtime directory, with mode 0400. It never enters the Nix store.

## Deliberate rotation/re-encryption

Enrollment refuses existing SSH material and an enrolled encrypted payload by
default. To re-encrypt the same validated dedicated pair explicitly:

```sh
antix-secrets-enroll --use-existing-key --replace-encrypted
```

For a replacement pair, move the old pair to a protected backup yourself first,
then use `antix-secrets-enroll --replace-encrypted`. Keys themselves are never
silently overwritten. If rotating age as well, back up the old identity securely,
install the new identity deliberately, update the public recipient, then enroll.
Register and test the replacement before revoking old GitHub access. Commit and
publish only the public recipient and encrypted payload. Restore from Bitwarden
on a fresh disposable VM to verify the full recovery chain.
