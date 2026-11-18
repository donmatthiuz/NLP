"""Entorno de pruebas con sesión: usuarios y clave en un directorio temporal, nunca los de keys/."""

import tempfile
from pathlib import Path

from licigt.plataforma.usuarios import hash_contrasena

CONTRASENAS = {"analista_demo": "clave-analista-demo", "lector_demo": "clave-lector-demo",
               "analista_b": "clave-analista-b"}
_USUARIOS = {"analista_demo": ("empresa_demo", "analista"), "lector_demo": ("empresa_demo", "lector"),
             "analista_b": ("empresa_b", "analista")}
_HASHES = {}


def preparar(carpeta: Path) -> dict:
    """Escribe clave y usuarios de prueba en carpeta y devuelve las variables de entorno que los apuntan."""
    import json
    if not _HASHES:  # scrypt es lento a propósito: se calcula una sola vez por proceso
        _HASHES.update({u: hash_contrasena(c) for u, c in CONTRASENAS.items()})
    (carpeta / "sesion.key").write_text("k" * 64)
    (carpeta / "usuarios.json").write_text(json.dumps({"usuarios": {
        u: {"hash": _HASHES[u], "tenant_id": t, "rol": r} for u, (t, r) in _USUARIOS.items()}}))
    return {"LICIGT_SESION_CLAVE_ARCHIVO": str(carpeta / "sesion.key"),
            "LICIGT_USUARIOS_ARCHIVO": str(carpeta / "usuarios.json"),
            "LICIGT_AUDITORIA_DIR": str(carpeta / "auditoria")}


def carpeta_temporal(prueba) -> Path:
    temporal = tempfile.TemporaryDirectory()
    prueba.addCleanup(temporal.cleanup)
    return Path(temporal.name)


def iniciar_sesion(cliente, usuario="analista_demo"):
    r = cliente.post("/api/sesion", json={"usuario": usuario, "contrasena": CONTRASENAS[usuario]})
    assert r.status_code == 204, r.text
    return r
