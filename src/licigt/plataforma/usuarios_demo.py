"""make usuarios-demo: crea, si no existen, la clave de sesión y los usuarios de la demo en keys/plataforma.

Las contraseñas se generan al azar y van solo a contrasenas_demo.txt; nunca se imprimen."""

import json
import os
import secrets
import sys
from pathlib import Path

from .rutas import ruta
from .usuarios import hash_contrasena

USUARIOS_DEMO = (("analista_demo", "empresa_demo", "analista"),
                 ("lector_demo", "empresa_demo", "lector"),
                 ("analista_b", "empresa_b", "analista"))


def _escribir_privado(destino: Path, texto: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        f.write(texto)


def crear(forzar: bool = False) -> list[str]:
    """Devuelve una línea por archivo, sin su contenido. forzar rehace usuarios y contraseñas (la clave se conserva)."""
    clave = ruta("LICIGT_SESION_CLAVE_ARCHIVO", "keys/plataforma/sesion.key")
    archivo_usuarios = ruta("LICIGT_USUARIOS_ARCHIVO", "keys/plataforma/usuarios.json")
    contrasenas = ruta("LICIGT_CONTRASENAS_DEMO_ARCHIVO", "keys/plataforma/contrasenas_demo.txt")
    informe = []
    if clave.exists():
        informe.append(f"existe\t{clave}")
    else:
        _escribir_privado(clave, secrets.token_hex(32))
        informe.append(f"creada\t{clave}")
    if forzar:
        archivo_usuarios.unlink(missing_ok=True)
        contrasenas.unlink(missing_ok=True)
    if archivo_usuarios.exists() or contrasenas.exists():
        informe.append(f"existe\t{archivo_usuarios}\tno se tocó; para rehacerlo: make usuarios-demo FORZAR=1")
        return informe
    generadas = {usuario: secrets.token_urlsafe(12) for usuario, _, _ in USUARIOS_DEMO}
    _escribir_privado(archivo_usuarios, json.dumps({"usuarios": {
        usuario: {"hash": hash_contrasena(generadas[usuario]), "tenant_id": tenant, "rol": rol}
        for usuario, tenant, rol in USUARIOS_DEMO}}, indent=2))
    _escribir_privado(contrasenas, "".join(f"{u}\t{c}\n" for u, c in generadas.items()))
    informe += [f"creado\t{archivo_usuarios}", f"creado\t{contrasenas}\tahí están las contraseñas; no se imprimen"]
    return informe


if __name__ == "__main__":
    print("\n".join(crear(forzar="--forzar" in sys.argv[1:])), file=sys.stdout)
