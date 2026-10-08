#!/usr/bin/env bash
set -euo pipefail
source "${ANTIX_PATH:-$HOME/.antix}/commands/common.sh"
normal_user
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || die 'Requires aarch64 Linux.'
source /etc/os-release
[[ " $ID ${ID_LIKE:-} " == *' debian '* ]] || die 'Requires Debian-compatible userspace.'
command -v sudo >/dev/null || die 'sudo is required.'
sudo -v
if ! command -v nix >/dev/null || ! dpkg-query -W -f='${Status}' nix-setup-systemd 2>/dev/null | grep -q 'install ok installed'; then
  sudo apt-get update
  sudo apt-get install -y nix-bin nix-setup-systemd
fi
# Debian's nix-setup-systemd post-install may start nix-daemon.service before
# nix-daemon.socket. Systemd then refuses to listen on the socket because its
# service is already active. Use socket activation exclusively: keep the service
# disabled at boot, and stop it only when it blocks an inactive socket.
sudo systemctl daemon-reload || die 'Could not reload systemd units after installing Debian Nix.'
sudo systemctl disable nix-daemon.service || die 'Could not disable independent Nix daemon service startup.'
if ! sudo systemctl is-active --quiet nix-daemon.socket &&
   sudo systemctl is-active --quiet nix-daemon.service; then
  printf 'Nix daemon is active before its socket; stopping it for socket activation.\n'
  sudo systemctl stop nix-daemon.service || die 'Could not stop Nix daemon blocking socket activation.'
fi
if ! sudo systemctl enable --now nix-daemon.socket; then
  printf 'Initial Nix socket start returned nonzero; checking actual socket state.\n' >&2
fi
if ! sudo systemctl is-active --quiet nix-daemon.socket; then
  printf 'Nix daemon socket is inactive; retrying after clearing the service/socket conflict.\n' >&2
  if sudo systemctl is-active --quiet nix-daemon.service; then
    sudo systemctl stop nix-daemon.service || die 'Could not stop Nix daemon blocking socket retry.'
  fi
  sudo systemctl reset-failed nix-daemon.socket || true
  sudo systemctl daemon-reload || true
  sudo systemctl start nix-daemon.socket || true
fi
if ! sudo systemctl is-active --quiet nix-daemon.socket; then
  printf 'Nix daemon socket remains inactive. Systemd diagnostics:\n' >&2
  sudo systemctl status nix-daemon.socket nix-daemon.service --no-pager -l >&2 || true
  sudo journalctl -b -u nix-daemon.socket -u nix-daemon.service --no-pager -n 80 >&2 || true
  die 'Nix socket startup failed. Do not wipe /nix; inspect the diagnostics above.'
fi
# Verify that socket activation actually launches a usable daemon, not just
# that systemd reports a listening socket. Root is used before nix-users
# membership becomes active for the current login.
if ! sudo nix --extra-experimental-features nix-command store ping --store daemon; then
  sudo systemctl status nix-daemon.socket nix-daemon.service --no-pager -l >&2 || true
  sudo journalctl -b -u nix-daemon.socket -u nix-daemon.service --no-pager -n 80 >&2 || true
  die 'Nix daemon connection failed after socket activation.'
fi
getent group nix-users >/dev/null || sudo groupadd --system nix-users
sudo usermod -aG nix-users "$(id -un)"
mkdir -p "$HOME/.config/nix"
conf=$HOME/.config/nix/nix.conf
[[ ! -L $conf ]] || die 'Refusing symlinked nix.conf.'
# Validate managed content before changing either file.
managed=$HOME/.config/nix/antix.conf
settings='experimental-features = nix-command flakes
max-jobs = 1
cores = 1'
legacy="$settings
max-substitution-jobs = 2
http-connections = 4"
if [[ -e $managed || -L $managed ]]; then
  [[ ! -L $managed && -f $managed ]] || die 'Refusing symlinked or non-regular antix.conf.'
  existing=$(cat "$managed")
  [[ $existing == "$settings" || $existing == "$legacy" || $existing == 'experimental-features = nix-command flakes' ]] || die 'Unexpected existing antix.conf; review manually.'
fi
[[ ! -e $conf || -f $conf ]] || die 'Refusing non-regular nix.conf.'
tmp=$(mktemp "$HOME/.config/nix/.antix.XXXXXX")
printf '%s\n' "$settings" > "$tmp"
mv "$tmp" "$managed"
# Add a dedicated include without replacing unrelated user configuration.
touch "$conf"
line='!include antix.conf'
grep -Fxq "$line" "$conf" || printf '\n%s\n' "$line" >> "$conf"
if [[ " $(id -nG) " != *' nix-users '* ]]; then
  # usermod updated /etc/group, but this shell still has its old credentials.
  # sg creates a single child process with nix-users active, without requiring
  # a VM restart or giving the Home Manager build root privileges.
  command -v sg >/dev/null || die 'The Debian sg utility is required to activate nix-users without logging out.'
  printf 'Activating Home Manager with the new nix-users group (no VM restart needed).\n'
  export ANTIX_PATH="$repo"
  # ANTIX_PATH is deliberately expanded in sg's child shell, not here.
  # shellcheck disable=SC2016
  sg nix-users -c 'exec bash "$ANTIX_PATH/commands/antix-rebuild.sh"' ||
    die 'Could not rebuild as nix-users. Verify group membership with: getent group nix-users'
else
  bash "$repo/commands/antix-rebuild.sh"
fi
# Android Terminal may launch Bash directly, ignoring the passwd login shell.
# Append a small, idempotent hook; never replace the user's existing dotfiles.
install_shell_hook() {
  local target=$1
  local begin='# >>> antix-shell-init >>>'
  local end='# <<< antix-shell-init <<<'
  [[ ! -L $target && ( ! -e $target || -f $target ) ]] ||
    die "Refusing non-regular or symlinked shell startup file: $target"
  if [[ -f $target ]] && grep -Fqx "$begin" "$target"; then
    grep -Fqx "$end" "$target" ||
      die "Incomplete Antix startup hook in $target"
    return
  fi
  # Refuse a stray end marker rather than appending to a broken managed block.
  if [[ -f $target ]] && grep -Fqx "$end" "$target"; then
    die "Unexpected Antix startup hook marker in $target"
  fi
  # The literal $HOME expands when the startup file is sourced, not now.
  # shellcheck disable=SC2016
  printf '\n%s\n. "$HOME/.antix/commands/antix-shell-init.sh"\n%s\n' \
    "$begin" "$end" >> "$target"
}
# Bash login reads the first existing file in this priority order.
login_rc=$HOME/.profile
for candidate in "$HOME/.bash_profile" "$HOME/.bash_login"; do
  if [[ -e $candidate || -L $candidate ]]; then
    login_rc=$candidate
    break
  fi
done
install_shell_hook "$login_rc"
install_shell_hook "$HOME/.bashrc"
export PATH="$HOME/.nix-profile/bin:$PATH"
shell=$HOME/.nix-profile/bin/zsh
if [[ -x $shell && $(getent passwd "$(id -un)" | cut -d: -f7) != "$shell" ]]; then
  grep -Fxq "$shell" /etc/shells || printf '%s\n' "$shell" | sudo tee -a /etc/shells >/dev/null
  sudo chsh -s "$shell" "$(id -un)" || printf 'Could not change login shell; run zsh manually.\n'
fi
printf 'Stage A activated with verified interactive Oh My Zsh (clean theme, git plugin). Start a fresh login. Git remains on HTTPS.\n'
