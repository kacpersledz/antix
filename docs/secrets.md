# Antix secrets and recovery

Antix has its own age identity and Ed25519 GitHub SSH key. Bitwarden contains
only the private `AGE-SECRET-KEY`; Git contains the public age recipient and
SOPS-encrypted dedicated GitHub SSH private key. No plaintext private key or age
identity is committed or placed in Nix expressions.

## First enrollment: once on a trusted Nix machine

The current repository is already enrolled. Keep this procedure for deliberately
recreating or rotating the enrollment in the future; it is not part of normal
Android recovery.

Run this **single copy/paste command** once on any already-working trusted Nix
machine as your normal user. It needs no Antix clone, `~/.antix`, Home Manager,
existing age identity, Antix helper or `gh auth login`. Nix temporarily provides
all dependencies; the command enables flakes for this invocation only.

```sh
nix --extra-experimental-features "nix-command flakes" shell nixpkgs#bash nixpkgs#age nixpkgs#sops nixpkgs#openssh nixpkgs#coreutils nixpkgs#gnused nixpkgs#gnugrep -c bash -c 'set -euo pipefail; set +x; umask 077; OUT="$HOME/antix-enrollment-$(date +%Y%m%d-%H%M%S)"; [[ ! -e "$OUT" && ! -L "$OUT" ]] || { printf "Refusing existing output: %s\n" "$OUT" >&2; exit 1; }; mkdir -- "$OUT"; mkdir -- "$OUT/secrets"; TMP="$(mktemp -d)"; cleanup(){ rm -rf -- "$TMP"; }; trap cleanup EXIT; trap "exit 1" HUP INT TERM; age-keygen -o "$OUT/AGE-SECRET-KEY.txt" 2>/dev/null; chmod 600 "$OUT/AGE-SECRET-KEY.txt"; RECIPIENT="$(age-keygen -y "$OUT/AGE-SECRET-KEY.txt")"; [[ "$RECIPIENT" == age1* && $(printf "%s\n" "$RECIPIENT" | wc -l) -eq 1 ]] || { echo "Invalid age recipient" >&2; exit 1; }; ssh-keygen -q -t ed25519 -N "" -C antix-github -f "$TMP/id_ed25519"; cp "$TMP/id_ed25519.pub" "$OUT/github-ssh.pub"; printf "creation_rules:\n  - path_regex: secrets/[^/]+[.]yaml$\n    age: %s\n" "$RECIPIENT" > "$OUT/.sops.yaml"; { printf "github_ssh_private_key: |\n"; sed "s/^/  /" "$TMP/id_ed25519"; } > "$TMP/plain.yaml"; unset SOPS_KMS_ARN SOPS_PGP_FP SOPS_GCP_KMS_IDS SOPS_HUAWEICLOUD_KMS_IDS SOPS_AZURE_KEYVAULT_URLS SOPS_VAULT_URIS; sops --config "$OUT/.sops.yaml" --encrypt --age "$RECIPIENT" --filename-override "$OUT/secrets/github-ssh-key.yaml" --input-type yaml --output-type yaml "$TMP/plain.yaml" > "$TMP/encrypted.yaml"; grep -q "^sops:" "$TMP/encrypted.yaml"; if grep -q "BEGIN OPENSSH PRIVATE KEY" "$TMP/encrypted.yaml"; then echo "Encrypted output contains plaintext SSH key material" >&2; exit 1; fi; SOPS_AGE_KEY_FILE="$OUT/AGE-SECRET-KEY.txt" sops --config "$OUT/.sops.yaml" --decrypt --input-type yaml --extract "[\"github_ssh_private_key\"]" --output-type binary "$TMP/encrypted.yaml" > "$TMP/decrypted"; chmod 600 "$TMP/decrypted"; ssh-keygen -y -P "" -f "$TMP/decrypted" >/dev/null; cmp -s "$TMP/id_ed25519" "$TMP/decrypted"; mv "$TMP/encrypted.yaml" "$OUT/secrets/github-ssh-key.yaml"; printf "\nAntix enrollment created at:\n  %s\n\nPublic age recipient:\n  %s\n\nNext:\n  1. Save AGE-SECRET-KEY.txt in Bitwarden.\n  2. Register github-ssh.pub in GitHub.\n  3. Copy .sops.yaml into the Antix repo.\n  4. Copy secrets/github-ssh-key.yaml into the Antix repo.\n  5. Review and commit/publish only those two public/encrypted files.\n  6. After verifying storage and registration, remove this local enrollment directory.\n" "$OUT" "$RECIPIENT"'
```

On success, the only persistent artifacts are:

```text
~/antix-enrollment-YYYYMMDD-HHMMSS/
├── .sops.yaml
├── AGE-SECRET-KEY.txt
├── github-ssh.pub
└── secrets/
    └── github-ssh-key.yaml
```

The command uses `set -euo pipefail`, disables tracing and applies `umask 077`.
Output directory creation refuses existing paths, including symlinks. The age
identity is brand new, separate from Wintix, and mode 0600. Neither private key
is printed or placed in the Nix store. The unencrypted Ed25519 SSH private key,
plaintext YAML and decrypted verification copy exist only in a temporary
directory, removed on exit or a handled signal. The runtime SSH key deliberately
has no passphrase: SOPS/age protects it and permits noninteractive restoration.

Encryption explicitly uses the generated recipient and generated `.sops.yaml`,
with inherited alternative SOPS recipient selections cleared. It checks for SOPS
metadata and rejects a plaintext OpenSSH key marker, decrypts the newly generated
ciphertext using the new age file, validates the extracted OpenSSH key, and
compares it byte-for-byte with the source. Only then is ciphertext moved into
`secrets/github-ssh-key.yaml`. A failure may leave an incomplete output directory;
resolve it manually and do not distribute incomplete artifacts. The helper never
registers keys or contacts Bitwarden/GitHub on your behalf.

Distribute the four artifacts manually:

| Artifact | Destination |
| --- | --- |
| `AGE-SECRET-KEY.txt` | Bitwarden: only the private Antix age identity; **never Git** |
| `github-ssh.pub` | GitHub SSH keys: register the public Ed25519 key |
| `.sops.yaml` | Antix repository: copy over the recipient placeholder |
| `secrets/github-ssh-key.yaml` | Antix repository: copy over the encrypted-payload placeholder |

After copying into your repository checkout, review and commit **only**:

```text
.sops.yaml
secrets/github-ssh-key.yaml
```

Publish those two public/encrypted files to public `master` through your normal
review flow. Do not copy the enrollment directory into Git and do not alter
`secrets/enrollment-placeholder.txt`. The plaintext SSH private key is ephemeral
and does not need a separate backup: the encrypted repository payload restores it.

Confirm the age identity is retrievable from Bitwarden, GitHub has the public
SSH key, and the two repository artifacts are committed/published. Then remove
the local `antix-enrollment-*` directory. Ordinary `rm` does not guarantee forensic
secure erasure on flash/SSD; choose storage handling appropriate to your machine.
Do not print the age identity while transferring it to your own Bitwarden UI.

## Disposable VM recovery

After first enrollment publishes the two repository artifacts to `master`,
normal fresh Android recovery remains:

```sh
curl -fsSL https://raw.githubusercontent.com/kacpersledz/antix/master/install.sh | bash
```

This clones public Antix, bootstraps Debian Nix and standalone Home Manager,
restores the age identity from Bitwarden, decrypts the dedicated GitHub SSH key
with sops-nix, and verifies SSH before switching the remote. If `nix-users`
membership is inactive, start a new Debian login/session and resume with
`bash ~/.antix/bootstrap.sh`. Android normally generates neither a new age
identity nor a new SSH key. At the hidden terminal prompt paste the
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

`antix-secrets-enroll` remains available for deliberate rotation/re-enrollment
and advanced recovery on an existing Antix checkout. It is not the recommended
first-enrollment path. Restore the matching identity with
`antix-secrets-bootstrap` before using this helper.

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
