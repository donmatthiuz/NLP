"""Sesión sin estado en el servidor: cookie con la carga en base64url y su firma HMAC-SHA256."""

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from .rutas import ruta
from .usuarios import ROLES

NOMBRE_COOKIE = "licigt_sesion"
LARGO_MINIMO_CLAVE = 32


class SesionNoConfigurada(RuntimeError):
    """Falta la clave de firma; el mensaje nunca incluye su valor."""


@dataclass(frozen=True)
class Sesion:
    usuario: str
    tenant_id: str
    rol: str


def leer_clave() -> bytes:
    archivo = ruta("LICIGT_SESION_CLAVE_ARCHIVO", "keys/plataforma/sesion.key")
    try:
        clave = archivo.read_bytes().strip()
    except OSError:
        raise SesionNoConfigurada("falta la clave de sesión: make usuarios-demo") from None
    if len(clave) < LARGO_MINIMO_CLAVE:
        raise SesionNoConfigurada("la clave de sesión es demasiado corta")
    return clave


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _desb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firma(clave: bytes, carga: str) -> str:
    return _b64(hmac.new(clave, carga.encode(), hashlib.sha256).digest())


def emitir(clave: bytes, usuario: str, tenant_id: str, rol: str, horas: float, ahora: float | None = None) -> str:
    if rol not in ROLES:
        raise ValueError("rol desconocido")
    vence = int((time.time() if ahora is None else ahora) + horas * 3600)
    carga = _b64(json.dumps({"u": usuario, "t": tenant_id, "r": rol, "exp": vence},
                            separators=(",", ":"), sort_keys=True).encode())
    return f"{carga}.{_firma(clave, carga)}"


def verificar(valor, clave: bytes, ahora: float | None = None) -> Sesion | None:
    """La sesión del valor, o None si está alterado, vencido o mal formado."""
    try:
        carga, firma = valor.split(".")
        if not hmac.compare_digest(_firma(clave, carga).encode(), firma.encode()):
            return None
        datos = json.loads(_desb64(carga))
        usuario, tenant_id, rol, vence = datos["u"], datos["t"], datos["r"], datos["exp"]
    except (AttributeError, ValueError, KeyError, TypeError, binascii.Error):
        return None
    if not (isinstance(usuario, str) and isinstance(tenant_id, str) and rol in ROLES and isinstance(vence, int)):
        return None
    if (time.time() if ahora is None else ahora) >= vence:
        return None
    return Sesion(usuario=usuario, tenant_id=tenant_id, rol=rol)
