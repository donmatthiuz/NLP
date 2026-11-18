"""Auditoría: un archivo JSONL por día. Solo metadatos; nunca la pregunta, texto de PDF, contraseñas ni tokens."""

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone

from .rutas import ruta
from .sesion import SesionNoConfigurada, leer_clave

# Los campos de Contratos.md (rol 4 hacia rol 3) más los que el orquestador agrega; todo lo demás se descarta.
CAMPOS_CONSULTA = ("momento", "usuario", "tenant_id", "evento_id", "herramienta", "chunk_ids", "abstained",
                   "needs_human_review", "validacion", "latencia_ms", "error", "chunk_ids_citados",
                   "modelo_generador", "version_prompt")
CLAVES_INTENCION = ("accion", "motivo", "variante")
_cerrojo = threading.Lock()


def _escribir(linea: dict) -> None:
    """Una falla de escritura no cambia la respuesta a quien llama."""
    try:
        ahora = datetime.now(timezone.utc)
        linea = {"momento": ahora.isoformat(), **linea}
        carpeta = ruta("LICIGT_AUDITORIA_DIR", "data/auditoria")
        with _cerrojo:
            carpeta.mkdir(parents=True, exist_ok=True)
            with open(carpeta / f"{ahora:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def registrar(accion: str, resultado: str, *, usuario=None, tenant_id=None, **extra) -> None:
    _escribir({"usuario": usuario, "tenant_id": tenant_id, "accion": accion, "resultado": resultado, **extra})


def registrar_consulta(evento: dict) -> None:
    intencion = evento.get("intencion")
    intencion = {k: intencion[k] for k in CLAVES_INTENCION if k in intencion} if isinstance(intencion, dict) else None
    accion = intencion.get("accion") if intencion and intencion.get("accion") == "proponer_lista" else "consulta"
    linea = {k: evento[k] for k in CAMPOS_CONSULTA if k in evento}
    _escribir({**linea, "intencion": intencion, "accion": accion, "resultado": evento.get("error") or "ok"})


def registrar_lista(evento: dict) -> None:
    linea = {k: evento[k] for k in ("momento", "usuario", "tenant_id", "evento_id", "accion", "item_ids", "error")
             if k in evento}
    _escribir({**linea, "resultado": evento.get("error") or "ok"})


def registrar_login_fallido(usuario: str) -> None:
    """El nombre intentado se guarda solo como HMAC-SHA256 con la clave de sesión: sin la clave no se adivina."""
    try:
        clave = leer_clave()
    except SesionNoConfigurada:
        clave = b"sin-clave"
    huella = hmac.new(clave, usuario.encode(), hashlib.sha256).hexdigest()[:16]
    registrar("login", "credenciales_invalidas", usuario=f"hmac:{huella}")
