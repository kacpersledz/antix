#!/usr/bin/env bash
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
normal_user
# Runtime identity parameters are deliberately non-secret; no credential is read by Nix.
ANTIX_USER=$(id -un)
ANTIX_HOME=$HOME
export ANTIX_USER ANTIX_HOME
source "$repo/commands/zsh-checks.sh"
build_activation() {
  nix build --impure --no-update-lock-file --no-link --print-out-paths "$@" "path:$repo#homeConfigurations.antix.activationPackage"
}
activation=$(build_activation)
repaired=0
repair_activation() {
  (( repaired == 0 )) || die 'Zsh verification still fails after one repair; the Nix store/runtime may be unreliable. Inspect diagnostics; do not wipe /nix.'
  repaired=1
  printf 'antix: attempting one Nix closure repair before reactivation.\n' >&2
  # Nix 2.26 --repair hashes the build closure and substitutes/rebuilds corrupt
  # or missing paths. An ordinary build can reuse a registered corrupt output.
  activation=$(build_activation --repair) || die 'Nix repair failed; store/runtime reliability is unresolved.'
  zsh_artifact_check "$activation/home-files" || die 'Generated Zsh artifacts remain invalid after repair; store/runtime reliability is unresolved.'
}
# Check the actual generated outputs before linking them into HOME.
zsh_artifact_check "$activation/home-files" || repair_activation
"$activation/activate"
if ! zsh_active_check "$activation"; then
  repair_activation
  "$activation/activate"
  zsh_active_check "$activation" || die 'Activated Zsh artifacts remain invalid after repair.'
fi
zsh_runtime_check || die 'Interactive Zsh initialization failed despite artifact checks. Inspect startup errors and ~/.config/zsh/local.zsh; store/runtime reliability is unresolved.'
printf 'antix: Home Manager Zsh integrity and interactive startup verified.\n'
