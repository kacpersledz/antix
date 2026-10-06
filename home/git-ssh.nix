{ config, lib, ... }:
let
  enrolled = builtins.readFile ../secrets/github-ssh-key.yaml != builtins.readFile ../secrets/enrollment-placeholder.txt;
in {
  programs.git.enable = true;
  programs.git.settings.user = {
    name = "kacpersledz";
    email = "casper.sledx@gmail.com";
  };
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    settings."github.com" = {
      HostName = "github.com";
      User = "git";
      IdentitiesOnly = true;
      IdentityFile = if enrolled then config.sops.secrets.antix-github-ssh.path else "${config.home.homeDirectory}/.config/sops-nix/secrets/antix-github-ssh";
    };
  };
  sops = lib.mkIf enrolled {
    age.keyFile = "${config.home.homeDirectory}/.config/sops/age/keys.txt";
    defaultSopsFile = ../secrets/github-ssh-key.yaml;
    secrets.antix-github-ssh = { key = "github_ssh_private_key"; mode = "0400"; };
  };
  systemd.user.services = lib.mkIf enrolled {
    sops-nix.Unit.ConditionPathExists = "%h/.config/sops/age/keys.txt";
  };
}
