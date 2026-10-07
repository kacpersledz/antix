# Pure checks: inactive wrappers must never be imported into the HM profile.
let
  gitModule = import ../home/git.nix { };
  home = import ../home/default.nix {
    config.home.profileDirectory = "/home/antix-test/.nix-profile";
    lib.mkForce = value: value;
  };
in
assert gitModule.programs.git.settings.user == {
  name = "kacpersledz";
  email = "casper.sledx@gmail.com";
};
assert home.home.packages == [ ];
assert home.programs.home-manager.enable == false;
assert home.imports == [ ../home/zsh.nix ../home/git.nix ];
assert home.nix.package == null;
assert home.systemd.user.startServices == false;
assert home.targets.genericLinux.enable;
assert !home.targets.genericLinux.gpu.enable;
assert !home.xdg.mime.enable;
assert !home.programs.man.enable;
assert !home.manual.manpages.enable;
assert builtins.match ".*/usr/share/doc/nix-bin/examples/nix.sh.*" home.home.sessionVariablesExtra != null;
true
