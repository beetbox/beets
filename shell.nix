let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/030ba1976b7c0e1a67d9716b17308ccdab5b381e.tar.gz") {};
in pkgs.mkShell {
  packages = with pkgs; [
    pre-commit
    poetry
    poethepoet
  ];
  shellHook = ''
    LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib/:/run/opengl-driver/lib/
  '';
}

