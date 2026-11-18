# NixOS: entorno para los wheels de torch/sentence-transformers (sin nix-ld).
{ pkgs ? import <nixpkgs> {} }:
pkgs.mkShell {
  packages = [ pkgs.python312 pkgs.uv pkgs.poppler-utils ];  # pdfplumber: pip install -r src/licigt/ingesta/requirements.txt
  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ] + ":/run/opengl-driver/lib";
  shellHook = ''
    [ -d .venv ] || uv venv -p ${pkgs.python312}/bin/python3.12 .venv
    source .venv/bin/activate
  '';
}
