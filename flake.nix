{
  description = "Antix: disposable Android Debian development environment";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
    sops-nix.url = "github:Mic92/sops-nix";
    sops-nix.inputs.nixpkgs.follows = "nixpkgs";
  };
  outputs = inputs@{ nixpkgs, home-manager, sops-nix, ... }:
    let
      system = "aarch64-linux";
      pkgs = import nixpkgs { inherit system; };
      unstablePkgs = import inputs.nixpkgs-unstable { inherit system; };
      commands = import ./commands { inherit pkgs; };
    in {
      packages.${system} = commands;
      homeConfigurations.antix = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = { inherit unstablePkgs commands; };
        modules = [ sops-nix.homeManagerModules.sops ./home ];
      };
    };
}
