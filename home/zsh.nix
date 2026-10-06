{ lib, ... }:

{
  programs.zsh = {
    enable = true;
    enableCompletion = true;

    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;

    oh-my-zsh = {
      enable = true;
      theme = "clean";
      plugins = [ "git" ];
    };

    # Machine-local or private extensions can provide this file without
    # making the public Wintix flake depend on their source repository.
    initContent = lib.mkAfter ''
      [[ -r "$HOME/.config/zsh/local.zsh" ]] && source "$HOME/.config/zsh/local.zsh"
    '';
  };
}
