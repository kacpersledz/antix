{ config, lib, ... }:
let
  user = builtins.getEnv "ANTIX_USER";
  home = builtins.getEnv "ANTIX_HOME";
  # genericLinux's default profile hook references pkgs.nix even when
  # nix.package is null. Use the profile script shipped by Debian nix-bin.
  debianNixProfile = ''
    if [ -r /usr/share/doc/nix-bin/examples/nix.sh ]; then
      . /usr/share/doc/nix-bin/examples/nix.sh
    fi
  '';
in {
  assertions = [ { assertion = user != "" && home != ""; message = "Use antix-rebuild to supply the non-secret Debian user/home parameters."; } ];
  imports = [ ./zsh.nix ./git.nix ];
  home.username = user;
  home.homeDirectory = home;
  home.stateVersion = "26.05";
  home.packages = [ ];
  programs.home-manager.enable = false;
  targets.genericLinux.enable = true;
  # This terminal baseline needs no GPU integration, desktop MIME tools or manuals.
  targets.genericLinux.gpu.enable = false;
  xdg.mime.enable = false;
  programs.man.enable = false;
  manual.manpages.enable = false;
  nix.package = null;
  # No user services in this baseline; avoid the Rust-based sd-switch closure.
  systemd.user.startServices = false;
  home.sessionPath = [ "${config.home.profileDirectory}/bin" ];
  home.sessionVariablesExtra = lib.mkForce (debianNixProfile + ''
    export TERM="$TERM"
  '');
  programs.bash.initExtra = lib.mkForce (debianNixProfile + ''
    . "${config.home.profileDirectory}/etc/profile.d/hm-session-vars.sh"
  '');
}
