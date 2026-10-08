#!/usr/bin/env bash
# Sourced by the Antix-managed hooks in the user's Bash startup files.
# Never replace non-interactive Bash (installers, scripts, CI, ssh commands).
case $- in *i*) ;; *) return 0 ;; esac

profile_bin="$HOME/.nix-profile/bin"
case ":$PATH:" in
  *":$profile_bin:"*) ;;
  *) export PATH="$profile_bin:$PATH" ;;
esac
unset profile_bin

# Users can explicitly request Bash with ANTIX_KEEP_BASH=1 bash.
[[ ${ANTIX_KEEP_BASH:-0} == 1 ]] && return 0
[[ -t 0 && -t 1 ]] || return 0

# Missing/incomplete profile: keep the existing Bash session usable.
[[ -x "$HOME/.nix-profile/bin/zsh" ]] || return 0
exec "$HOME/.nix-profile/bin/zsh" -l
