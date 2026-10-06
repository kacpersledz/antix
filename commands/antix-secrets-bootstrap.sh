#!/usr/bin/env bash
set +x
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
normal_user
expected=$(expected_recipient)
key_dir=$HOME/.config/sops/age
key_file=$key_dir/keys.txt
umask 077
for path in "$HOME/.config" "$HOME/.config/sops" "$key_dir" "$key_file"; do
  [[ ! -L $path ]] || die 'Refusing symlinked secret path.'
done
if [[ -e $key_file ]]; then
  identity_valid || die 'Unexpected existing age material; refusing overwrite.'
  [[ $(stat -c %u "$key_file") == $(id -u) ]] || die 'Unexpected age file owner.'
  chmod 0700 "$key_dir"
  chmod 0600 "$key_file"
  printf 'Correct Antix identity already installed.\n'
  exit 0
fi
mkdir -p "$key_dir"
chmod 0700 "$key_dir"
tmp=$(mktemp "$key_dir/.keys.XXXXXX")
tty_state=''
cleanup() {
  if [[ -n $tty_state ]]; then stty "$tty_state" </dev/tty || true; fi
  rm -f -- "$tmp"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
# Disable echo before showing the prompt, so an immediate paste cannot race read -s.
tty_state=$(stty -g </dev/tty) || die 'A controlling terminal is required.'
stty -echo </dev/tty
printf 'Paste Antix AGE-SECRET-KEY from Bitwarden: ' >&2
IFS= read -r -s identity </dev/tty
stty "$tty_state" </dev/tty
tty_state=''
printf '\n' >&2
printf '%s\n' "$identity" > "$tmp"
unset identity
actual=$(age-keygen -y "$tmp" 2>/dev/null) || die 'Malformed age identity.'
[[ $actual == "$expected" ]] || die 'Age recipient mismatch; nothing installed.'
ln "$tmp" "$key_file" || die 'Identity appeared concurrently; refusing overwrite.'
printf 'Antix identity installed.\n'
