{ pkgs }:
let
  names = [ "bootstrap" "rebuild" "update" "secrets-bootstrap" "secrets-enroll" "doctor" "codex" ];
  make = name: pkgs.writeShellApplication {
    name = "antix-${name}";
    runtimeInputs = with pkgs; [ bash coreutils gnugrep gnused git curl jq age sops openssh shpool nix util-linux ];
    # Debian privilege/systemd tools come from the host. Sources stay in the checkout
    # so enrollment and local recovery always operate on the editable repository.
    text = ''
      repo="''${ANTIX_PATH:-$HOME/.antix}"
      exec bash "$repo/commands/antix-${name}.sh" "$@"
    '';
  };
in builtins.listToAttrs (map (name: { name = "antix-${name}"; value = make name; }) names)
