#!/usr/bin/env bash
# Shared by rebuild, doctor and ARM64 CI. Home Manager owns all dotfiles.
# Literal shell snippets are checked in generated content.
# shellcheck disable=SC2016
zsh_artifact_check() {
  local directory=$1 name target failed=0
  for name in .zshrc .zshenv; do
    target=$(readlink -f -- "$directory/$name") || target=
    if [[ -z $target || ! -f $target || ! -s $target ]]; then
      printf 'antix: missing, broken or empty generated %s: %s\n' "$name" "$directory/$name" >&2
      failed=1
      continue
    fi
    # Nix verifies the on-disk NAR hash, not the evaluated configuration.
    if ! nix-store --verify-path "$target"; then
      printf 'antix: Nix integrity verification failed: %s\n' "$target" >&2
      failed=1
    fi
    if [[ $name == .zshrc ]]; then
      if ! grep -Eq '^plugins=\(.*\bgit\b.*\)' "$target" ||
         ! grep -Eq "^ZSH_THEME=['\"]?clean['\"]?$" "$target" ||
         ! grep -Fq 'source $ZSH/oh-my-zsh.sh' "$target"; then
        printf 'antix: generated .zshrc lacks expected Oh My Zsh initialization: %s\n' "$target" >&2
        failed=1
      fi
    elif ! grep -Fq 'hm-session-vars.sh' "$target" || ! grep -Fq '.nix-profile/bin:' "$target"; then
      printf 'antix: generated .zshenv lacks Home Manager session/profile setup: %s\n' "$target" >&2
      failed=1
    fi
  done
  (( failed == 0 ))
}
zsh_active_check() {
  local activation=$1 name expected actual
  zsh_artifact_check "$HOME" || return 1
  for name in .zshrc .zshenv; do
    [[ -L $HOME/$name ]] || { printf 'antix: %s is not a Home Manager symlink\n' "$HOME/$name" >&2; return 1; }
    expected=$(readlink -f -- "$activation/home-files/$name") || return 1
    actual=$(readlink -f -- "$HOME/$name") || return 1
    [[ $actual == "$expected" ]] || { printf 'antix: activated %s does not match built generation\n' "$name" >&2; return 1; }
  done
}
zsh_runtime_check() {
  # Remove inherited ZDOTDIR, HM sentinels and shell options. Keep the real HOME
  # and minimal Debian PATH; .zshenv must supply the Home Manager profile itself.
  # shellcheck disable=SC2016
  env -i HOME="$HOME" USER="$(id -un)" LOGNAME="$(id -un)" \
    PATH=/usr/bin:/bin TERM="${TERM:-dumb}" \
    "$HOME/.nix-profile/bin/zsh" -ic '
      [[ -n $ZSH && -r $ZSH/oh-my-zsh.sh ]] || exit 1
      [[ $ZSH_THEME == clean && ${plugins[(Ie)git]} -gt 0 ]] || exit 1
      (( $+functions[omz] )) || exit 1
      (( $+functions[git_prompt_info] )) || exit 1
      [[ ${path[(Ie)$HOME/.nix-profile/bin]} -gt 0 ]] || exit 1
      print -r -- "PASS interactive Zsh: Oh My Zsh, clean theme, git plugin"
    '
}
