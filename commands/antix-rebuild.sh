#!/usr/bin/env bash
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
normal_user
# Runtime identity parameters are deliberately non-secret; no credential is read by Nix.
export ANTIX_USER="$(id -un)" ANTIX_HOME="$HOME"
activation=$(nix build --impure --no-update-lock-file --no-link --print-out-paths "path:$repo#homeConfigurations.antix.activationPackage")
"$activation/activate"
