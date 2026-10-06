#!/usr/bin/env bash
set -euo pipefail
# shpool attach creates the named session only when absent and reattaches otherwise.
exec shpool attach --cmd codex antix-codex
