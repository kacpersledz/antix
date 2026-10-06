#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"

if [[ $(id -u) -eq 0 ]]; then
  printf 'antix-secrets-enroll: run this command as your normal user; it operates on user-owned secret material.\n' >&2
  exit 1
fi

die() {
  printf 'antix-secrets-enroll: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf 'Usage: antix-secrets-enroll [--use-existing-key] [--replace-encrypted]\n'
}

use_existing=false
replace_encrypted=false
while (( $# )); do
  case $1 in
    --use-existing-key) use_existing=true ;;
    --replace-encrypted) replace_encrypted=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

config_home=$HOME/.config
age_file=$config_home/sops/age/keys.txt
ssh_dir=$HOME/.ssh
ssh_key=$ssh_dir/antix_github_ed25519
repo=${ANTIX_PATH:-"$HOME/.antix"}
sops_config=$repo/.sops.yaml
encrypted_file=$repo/secrets/github-ssh-key.yaml

identity_valid || die "age identity does not match the intended Antix recipient"
[[ -f $age_file ]] || die "missing age identity at $age_file; restore it with antix-secrets-bootstrap first"
recipient=$(age-keygen -y "$age_file" 2>/dev/null) || die "invalid age identity at $age_file"
[[ $recipient == age1* ]] || die "age-keygen returned an invalid public recipient"
[[ -f $sops_config ]] || die "missing $sops_config"
if ! grep -E "^[[:space:]]*age:[[:space:]]*$recipient([[:space:]]*#.*)?$" "$sops_config" >/dev/null; then
  die ".sops.yaml is not configured for $recipient; update the public age recipient deliberately, review the change, then rerun"
fi

for path in "$ssh_dir" "$ssh_key" "$ssh_key.pub" "$encrypted_file"; do
  [[ ! -L $path ]] || die "refusing symlinked credential path"
done
if [[ -e $encrypted_file ]] && ! cmp -s "$encrypted_file" "$repo/secrets/enrollment-placeholder.txt"; then
  $replace_encrypted || die "$encrypted_file already contains enrolled data; use --replace-encrypted only after reviewing the rotation plan"
fi

mkdir -p -- "$ssh_dir"
chmod 0700 -- "$ssh_dir"
if [[ -e $ssh_key || -e $ssh_key.pub ]]; then
  $use_existing || die "SSH key material already exists at $ssh_key; refusing to overwrite it (use --use-existing-key to re-encrypt it deliberately)"
  [[ -f $ssh_key && -f $ssh_key.pub ]] || die "incomplete existing SSH key pair at $ssh_key; refusing to modify it"
  derived_public=$(ssh-keygen -y -P '' -f "$ssh_key" 2>/dev/null) || die "existing SSH private key is invalid"
  IFS=' ' read -r derived_type derived_data _ <<<"$derived_public"
  IFS=' ' read -r public_type public_data _ <"$ssh_key.pub"
  [[ $derived_type == ssh-ed25519 ]] || die "existing SSH key must be Ed25519"
  [[ "$public_type $public_data" == "$derived_type $derived_data" ]] || die "existing SSH public key does not match its private key"
else
  $use_existing && die "--use-existing-key was requested, but $ssh_key does not exist"
  ssh-keygen -q -t ed25519 -N '' -C 'antix-github' -f "$ssh_key"
fi
chmod 0600 -- "$ssh_key"
chmod 0644 -- "$ssh_key.pub"

runtime_dir=${XDG_RUNTIME_DIR:-$config_home}
runtime_dir=$(realpath "$runtime_dir")
case $runtime_dir/ in
  "$repo/"*|/nix/store/*) die "plaintext scratch directory must be outside the checkout and Nix store" ;;
esac
tmp_dir=$(mktemp -d "$runtime_dir/antix-enroll.XXXXXX")
chmod 0700 -- "$tmp_dir"
plain=$tmp_dir/github-ssh-key.yaml
decrypted=$tmp_dir/antix-github-ssh
mkdir -p -- "$repo/secrets"
encrypted=$(mktemp "$repo/secrets/.github-ssh-key.yaml.XXXXXX")
chmod 0600 -- "$encrypted"
cleanup() {
  rm -rf -- "$tmp_dir"
  rm -f -- "$encrypted"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
{
  # Preserve the SSH private key's required final newline in the YAML scalar.
  printf 'github_ssh_private_key: |\n'
  while IFS= read -r line || [[ -n $line ]]; do printf '  %s\n' "$line"; done <"$ssh_key"
} >"$plain"
chmod 0600 -- "$plain"

(cd "$repo" && sops --encrypt --filename-override secrets/github-ssh-key.yaml "$plain") >"$encrypted"
grep -Eq '^sops:' "$encrypted" || die "SOPS output has no metadata section"
if grep -F 'BEGIN OPENSSH PRIVATE KEY' "$encrypted" >/dev/null; then
  die "SOPS output still contains a plaintext OpenSSH private-key header"
fi
if ! SOPS_AGE_KEY_FILE="$age_file" sops --decrypt --input-type yaml --extract '["github_ssh_private_key"]' --output-type binary "$encrypted" >"$decrypted"; then
  die "SOPS could not decrypt and extract the SSH private key"
fi
chmod 0600 -- "$decrypted"
ssh-keygen -y -P '' -f "$decrypted" >/dev/null 2>&1 || die "decrypted SOPS payload is not a valid OpenSSH private key"
cmp -s -- "$ssh_key" "$decrypted" || die "decrypted SOPS payload does not exactly match the source SSH private key"
# The encrypted temporary file is deliberately created beside the destination,
# so this rename is an atomic same-filesystem replacement.
mv -f -- "$encrypted" "$encrypted_file"
chmod 0600 -- "$encrypted_file"

printf 'GitHub SSH public key (safe to register):\n'
cat -- "$ssh_key.pub"
printf '\nRegister that public key with GitHub, commit only .sops.yaml and %s, then verify:\n' "$encrypted_file"
printf '  systemctl --user restart sops-nix\n  ssh -T git@github.com\n'
