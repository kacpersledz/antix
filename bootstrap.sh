#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export ANTIX_PATH=$repo
exec bash "$repo/commands/antix-bootstrap.sh" "$@"
