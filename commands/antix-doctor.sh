#!/usr/bin/env bash
# These expressions expand in the child bash, not this script.
# shellcheck disable=SC2016
set +x
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
failures=0
check() {
  local label=$1
  shift
  if "$@" >/dev/null 2>&1; then printf 'PASS %s\n' "$label"; else printf 'FAIL %s\n' "$label"; failures=$((failures+1)); fi
}
check Linux test "$(uname -s)" = Linux
check architecture test "$(uname -m)" = aarch64
check Debian bash -c '. /etc/os-release; [[ " $ID ${ID_LIKE:-} " == *" debian "* ]]'
check Nix command -v nix
if command -v nix >/dev/null; then nix --version; fi
check nix-daemon systemctl is-active nix-daemon.service
check nix-command/flakes bash -c 'nix config show --json | jq -e '\''."experimental-features".value | (index("nix-command") != null and index("flakes") != null)'\'''
check nix-users bash -c '[[ " $(id -nG) " == *" nix-users "* ]]'
check 'Home Manager activation' test -x "$HOME/.nix-profile/bin/zsh"
check 'Antix HTTPS remote' bash -c '[[ $(git -C "$1" remote get-url origin) == https://github.com/kacpersledz/antix.git ]]' _ "$repo"
for tool in git curl jq rg fd fzf zsh less unzip zip tree file which; do check "$tool" command -v "$tool"; done
check 'Zsh runtime' zsh --version
printf 'DEFERRED SSH recovery, age/SOPS/OpenSSH, shpool and Codex (Stages B-D)\n'
check 'Git author identity' bash -c '[[ -n $(git config --get user.name) && -n $(git config --get user.email) ]]'
(( failures == 0 ))
