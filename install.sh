#!/usr/bin/env bash
set -euo pipefail
[[ $(uname -s) == Linux && $(uname -m) == aarch64 && $(id -u) != 0 ]] || { echo 'Requires a normal user on aarch64 Debian Linux.' >&2; exit 1; }
. /etc/os-release
[[ " $ID ${ID_LIKE:-} " == *' debian '* ]] || { echo 'Requires Debian-compatible userspace.' >&2; exit 1; }
command -v sudo >/dev/null
if ! command -v git >/dev/null || ! command -v curl >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y git curl ca-certificates
fi
repo=$HOME/.antix
if [[ -e $repo || -L $repo ]]; then
  [[ ! -L $repo && -d $repo/.git ]] || { echo 'Unexpected ~/.antix; refusing replacement.' >&2; exit 1; }
  [[ $(git -C "$repo" rev-parse --show-toplevel) == "$repo" &&
     $(git -C "$repo" branch --show-current) == master &&
     -z $(git -C "$repo" status --porcelain --untracked-files=all) ]] || { echo 'Requires a clean master checkout.' >&2; exit 1; }
  origin=$(git -C "$repo" remote get-url origin)
  [[ $origin == https://github.com/kacpersledz/antix.git || $origin == git@github.com:kacpersledz/antix.git ]] || { echo 'Unexpected origin.' >&2; exit 1; }
  git -C "$repo" fetch https://github.com/kacpersledz/antix.git master
  git -C "$repo" merge --ff-only FETCH_HEAD
else
  git clone --branch master https://github.com/kacpersledz/antix.git "$repo"
fi
exec bash "$repo/bootstrap.sh"
