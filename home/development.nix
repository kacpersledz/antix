{ pkgs, unstablePkgs, ... }: {
  home.packages = with pkgs; [ git curl jq ripgrep fd fzf age sops openssh shpool zsh less unzip zip tree file which unstablePkgs.codex ];
  # No programs.codex module: ~/.codex remains entirely mutable.
}
