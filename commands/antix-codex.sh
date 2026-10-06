#!/usr/bin/env bash
set -euo pipefail
# --dir . starts new sessions in the invocation directory; existing sessions reattach.
exec shpool attach --dir . --cmd codex antix-codex
