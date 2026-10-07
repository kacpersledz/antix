{ ... }: {
  programs.git.enable = true;
  programs.git.settings.user = {
    name = "kacpersledz";
    email = "casper.sledx@gmail.com";
  };
}
