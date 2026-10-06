#!/usr/bin/env bash
# Shared helpers; never enable tracing in scripts handling credentials.
set +x
set -euo pipefail
repo=${ANTIX_PATH:-$HOME/.antix}
die() { printf 'antix: %s\n' "$*" >&2; exit 1; }
normal_user() { [[ $(id -u) != 0 ]] || die 'Run as your normal non-root user.'; }
expected_recipient() {
  local value
  value=$(sed -nE 's/^[[:space:]]*age:[[:space:]]*(age1[0-9a-z]+)[[:space:]]*$/\1/p' "$repo/.sops.yaml")
  [[ $value == age1* && $value != *$'\n'* ]] || die 'Antix enrollment required: set exactly one public age recipient in .sops.yaml.'
  printf '%s\n' "$value"
}
identity_valid() {
  local actual
  [[ ! -L $HOME/.config/sops/age/keys.txt && -f $HOME/.config/sops/age/keys.txt ]] || return 1
  actual=$(age-keygen -y "$HOME/.config/sops/age/keys.txt" 2>/dev/null) || return 1
  [[ $actual == "$(expected_recipient)" ]]
}
