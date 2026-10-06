{ commands, ... }:
let
  user = builtins.getEnv "ANTIX_USER";
  home = builtins.getEnv "ANTIX_HOME";
in {
  assertions = [ { assertion = user != "" && home != ""; message = "Use antix-rebuild to supply the non-secret Debian user/home parameters."; } ];
  imports = [ ./zsh.nix ./development.nix ./git-ssh.nix ];
  home.username = user;
  home.homeDirectory = home;
  home.stateVersion = "26.05";
  home.packages = builtins.attrValues commands;
  programs.home-manager.enable = true;
  targets.genericLinux.enable = true;
  systemd.user.startServices = "sd-switch";
}
