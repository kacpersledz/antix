#!/usr/bin/env bash
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
normal_user
[[ $# == 0 || ( $# == 1 && $1 == --checkout-only ) ]] || die 'Usage: antix-update [--checkout-only]'
[[ ! -L $repo && $(git -C "$repo" rev-parse --show-toplevel) == "$repo" ]] || die 'Unexpected checkout.'
[[ -z $(git -C "$repo" status --porcelain --untracked-files=all) ]] || die 'Checkout has local changes; preserve/review them before update.'
[[ $(git -C "$repo" branch --show-current) == master ]] || die 'Updates require the master branch.'
url=$(git -C "$repo" remote get-url origin)
[[ $url == https://github.com/kacpersledz/antix.git || $url == git@github.com:kacpersledz/antix.git ]] || die 'Unexpected origin.'
# Public HTTPS transport works even before SSH recovery.
git -C "$repo" fetch https://github.com/kacpersledz/antix.git master
git -C "$repo" merge --ff-only FETCH_HEAD
[[ ${1:-} == --checkout-only ]] || bash "$repo/commands/antix-rebuild.sh"
