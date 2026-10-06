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
sudo systemctl enable --now nix-daemon.socket nix-daemon.service
getent group nix-users >/dev/null || sudo groupadd --system nix-users
sudo usermod -aG nix-users "$(id -un)"
mkdir -p "$HOME/.config/nix"
conf=$HOME/.config/nix/nix.conf
[[ ! -L $conf ]] || die 'Refusing symlinked nix.conf.'
# Add a dedicated include without replacing the user's existing configuration.
touch "$conf"
line='!include antix.conf'
grep -Fxq "$line" "$conf" || printf '\n%s\n' "$line" >> "$conf"
managed=$HOME/.config/nix/antix.conf
if [[ -e $managed || -L $managed ]]; then
  [[ ! -L $managed && $(cat "$managed") == 'experimental-features = nix-command flakes' ]] || die 'Unexpected existing antix.conf; review manually.'
fi
tmp=$(mktemp "$HOME/.config/nix/.antix.XXXXXX")
printf 'experimental-features = nix-command flakes\n' > "$tmp"
mv "$tmp" "$HOME/.config/nix/antix.conf"
if [[ " $(id -nG) " != *' nix-users '* ]]; then
  die 'nix-users membership is not active. Log out of the Debian session and log back in (or restart the VM), then run: bash ~/.antix/bootstrap.sh'
fi
# Apt tools allow hidden recovery before the declarative environment exists.
if ! command -v age-keygen >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y age
fi
if ! cmp -s "$repo/secrets/github-ssh-key.yaml" "$repo/secrets/enrollment-placeholder.txt"; then
  bash "$repo/commands/antix-secrets-bootstrap.sh"
else
  printf 'Secrets are not enrolled yet; installing CLI environment without GitHub credentials. See docs/secrets.md.\n'
fi
bash "$repo/commands/antix-rebuild.sh"
export PATH="$HOME/.nix-profile/bin:$PATH"
if identity_valid && ! cmp -s "$repo/secrets/github-ssh-key.yaml" "$repo/secrets/enrollment-placeholder.txt"; then
  systemctl --user restart sops-nix
  [[ -f $HOME/.config/sops-nix/secrets/antix-github-ssh ]] || die "Decrypted SSH key unavailable."
  # GitHub returns status 1 even for successful authentication; inspect its greeting.
  if message=$(ssh -T -o BatchMode=yes -o ConnectTimeout=10 git@github.com 2>&1); then :; fi
  if [[ ${message:-} == *"Hi kacpersledz! You've successfully authenticated,"* ]]; then
    git -C "$repo" remote set-url origin git@github.com:kacpersledz/antix.git
  else
    printf 'GitHub SSH is not verified. Review host trust/key registration with ssh -T git@github.com, then rerun bootstrap. HTTPS retained.\n'
  fi
fi
shell=$HOME/.nix-profile/bin/zsh
if [[ -x $shell && $(getent passwd "$(id -un)" | cut -d: -f7) != "$shell" ]]; then
  grep -Fxq "$shell" /etc/shells || printf '%s\n' "$shell" | sudo tee -a /etc/shells >/dev/null
  sudo chsh -s "$shell" "$(id -un)" || printf 'Could not change login shell; run zsh manually.\n'
fi
printf 'Antix activated. A new login picks up Zsh. Run antix-doctor.\n'
