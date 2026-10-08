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
# Debian's package post-install scripts may report a transient systemctl job
# failure on a freshly booted Android VM. The socket is the readiness boundary:
# systemd starts nix-daemon.service on demand when a Nix client connects.
if ! sudo systemctl daemon-reload; then
  die 'Could not reload systemd units after installing Debian Nix.'
fi
if ! sudo systemctl enable --now nix-daemon.socket; then
  printf 'Initial Nix socket start returned nonzero; checking actual socket state.\n' >&2
fi
if ! sudo systemctl is-active --quiet nix-daemon.socket; then
  printf 'Nix daemon socket is not active; retrying start once after systemd reload.\n' >&2
  sudo systemctl daemon-reload || true
  sudo systemctl start nix-daemon.socket || true
fi
if ! sudo systemctl is-active --quiet nix-daemon.socket; then
  printf 'Nix daemon socket remains inactive. Systemd diagnostics:\n' >&2
  sudo systemctl status nix-daemon.socket nix-daemon.service --no-pager -l >&2 || true
  sudo journalctl -b -u nix-daemon.socket -u nix-daemon.service --no-pager -n 80 >&2 || true
  die 'Nix socket startup failed. Do not wipe /nix; inspect the diagnostics above.'
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
  die 'nix-users membership is not active. Log out of the Debian session and log back in (or restart the VM), then run: bash ~/.antix/bootstrap.sh'
fi
bash "$repo/commands/antix-rebuild.sh"
export PATH="$HOME/.nix-profile/bin:$PATH"
shell=$HOME/.nix-profile/bin/zsh
if [[ -x $shell && $(getent passwd "$(id -un)" | cut -d: -f7) != "$shell" ]]; then
  grep -Fxq "$shell" /etc/shells || printf '%s\n' "$shell" | sudo tee -a /etc/shells >/dev/null
  sudo chsh -s "$shell" "$(id -un)" || printf 'Could not change login shell; run zsh manually.\n'
fi
printf 'Stage A activated. Start a fresh login and verify: command -v zsh; zsh --version. Git remains on HTTPS.\n'
