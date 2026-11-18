"""Usuarios locales: contraseña con hashlib.scrypt y sal. El archivo vive en keys/plataforma, fuera del repo."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import tempfile
import threading
from dataclasses import dataclass

from .rutas import ruta

ROLES = ("analista", "lector")
N, R, P = 2**14, 8, 5  # equivalente OWASP con ~16 MiB (128 * N * R) por derivación
MAXMEM = 256 * 1024 * 1024  # holgado para verificar también hashes anteriores (N=2**17)
# Como mucho 2 derivaciones a la vez: acota memoria y CPU aunque lleguen muchos logins en paralelo.
_DERIVACIONES = threading.BoundedSemaphore(2)
_CERROJO_ARCHIVO = threading.Lock()
LARGO_MAXIMO = 1024  # bytes; hashlib recomienda acotar la contraseña


@dataclass(frozen=True)
class Usuario:
    usuario: str
    tenant_id: str
    rol: str


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


def _derivar(contrasena: bytes, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(contrasena, salt=sal, n=n, r=r, p=p, maxmem=MAXMEM, dklen=32)


def _derivar_limitado(contrasena: bytes, sal: bytes, n: int, r: int, p: int) -> bytes:
    with _DERIVACIONES:
        return _derivar(contrasena, sal, n, r, p)


def hash_contrasena(contrasena: str, sal: bytes | None = None) -> str:
    sal = sal or os.urandom(16)
    return f"scrypt${N}${R}${P}${_b64(sal)}${_b64(_derivar_limitado(contrasena.encode(), sal, N, R, P))}"


def verificar_contrasena(contrasena: str, almacenado) -> bool:
    """Comparación en tiempo constante; un hash mal formado nunca verifica ni lanza."""
    try:
        esquema, n, r, p, sal, esperado = almacenado.split("$")
        if esquema != "scrypt":
            return False
        crudo = contrasena.encode()
        if len(crudo) > LARGO_MAXIMO:
            return False
        calculado = _derivar_limitado(crudo, base64.b64decode(sal, validate=True), int(n), int(r), int(p))
        return hmac.compare_digest(calculado, base64.b64decode(esperado, validate=True))
    except (AttributeError, ValueError, TypeError, binascii.Error):
        return False


# Hash de un usuario inexistente: se verifica igual para que acertar el usuario no se note en el tiempo.
_HASH_FALSO = hash_contrasena("sin-usuario")


def _parametros(almacenado) -> tuple | None:
    try:
        _, n, r, p, _, _ = almacenado.split("$")
        return int(n), int(r), int(p)
    except (AttributeError, ValueError):
        return None


def cargar() -> dict:
    try:
        with open(ruta("LICIGT_USUARIOS_ARCHIVO", "keys/plataforma/usuarios.json"), encoding="utf-8") as f:
            usuarios = json.load(f).get("usuarios", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return usuarios if isinstance(usuarios, dict) else {}


def _actualizar_hash(usuario: str, viejo: str, contrasena: str) -> None:
    """Reescribe usuarios.json con el hash a los parámetros actuales: temporal 0600 más rename, sin dejar basura.

    Solo toca la entrada si su hash sigue siendo el viejo; una falla no impide el login."""
    destino = ruta("LICIGT_USUARIOS_ARCHIVO", "keys/plataforma/usuarios.json")
    temporal = None
    try:
        with _CERROJO_ARCHIVO:
            datos = json.loads(destino.read_text(encoding="utf-8"))
            if datos["usuarios"][usuario]["hash"] != viejo:
                return
            datos["usuarios"][usuario]["hash"] = hash_contrasena(contrasena)
            descriptor, temporal = tempfile.mkstemp(dir=destino.parent, prefix=".usuarios-", suffix=".tmp")
            with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                f.write(json.dumps(datos, indent=2))
            os.chmod(temporal, 0o600)
            os.replace(temporal, destino)
            temporal = None
    except (OSError, ValueError, KeyError, TypeError):
        pass
    finally:
        if temporal:
            try:
                os.unlink(temporal)
            except OSError:
                pass


def autenticar(usuario: str, contrasena: str) -> Usuario | None:
    registro = cargar().get(usuario)
    if not isinstance(registro, dict):
        verificar_contrasena(contrasena, _HASH_FALSO)
        return None
    if not verificar_contrasena(contrasena, registro.get("hash")):
        return None
    tenant_id, rol = registro.get("tenant_id"), registro.get("rol")
    if rol not in ROLES or not isinstance(tenant_id, str) or not tenant_id:
        return None
    if _parametros(registro["hash"]) != (N, R, P):
        _actualizar_hash(usuario, registro["hash"], contrasena)
    return Usuario(usuario=usuario, tenant_id=tenant_id, rol=rol)
