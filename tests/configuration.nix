# Pure regression checks for the selected author and package/wrapper inputs.
# A poisoned Nix attribute fails immediately if a module adds pkgs.nix again.
let
  names = [
    "bash" "coreutils" "gnugrep" "gnused" "git" "curl" "jq" "age"
    "sops" "openssh" "shpool" "util-linux" "ripgrep" "fd" "fzf"
    "zsh" "less" "unzip" "zip" "tree" "file" "which"
  ];
  pkgs = builtins.listToAttrs (map (name: { inherit name; value = name; }) names) // {
    nix = throw "Antix must use Debian's host Nix";
    writeShellApplication = args: args;
  };
  commands = import ../commands { inherit pkgs; };
  gitModule = import ../home/git-ssh.nix {
    config.home.homeDirectory = "/home/antix-test";
    lib.mkIf = condition: value: if condition then value else { };
  };
  development = import ../home/development.nix {
    inherit pkgs;
    unstablePkgs.codex = "codex";
  };
  home = import ../home/default.nix {
    inherit commands;
    config.home.profileDirectory = "/home/antix-test/.nix-profile";
    lib.mkForce = value: value;
  };
  noNix = packages: builtins.all (package: package != "nix") packages;
in
assert gitModule.programs.git.settings.user == {
  name = "kacpersledz";
  email = "casper.sledx@gmail.com";
};
assert noNix development.home.packages;
assert home.nix.package == null;
assert builtins.match ".*/usr/share/doc/nix-bin/examples/nix.sh.*" home.home.sessionVariablesExtra != null;
assert builtins.all (command: noNix command.runtimeInputs) (builtins.attrValues commands);
assert builtins.all (command: noNix command.runtimeInputs) home.home.packages;
true
