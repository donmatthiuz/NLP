"""Original del PDF: se sirve solo si la fila del documento existe para la empresa y el evento de la sesión."""

import os
import re
import zipfile
from pathlib import Path

from .rutas import RAIZ

DOC_ID = re.compile(r"[0-9a-f]{32}")
TENANT_ID = re.compile(r"[a-z0-9_]{1,64}")


def _carpetas() -> list[Path]:
    # El paquete de cada empresa vive en entregables (empresa_demo) o en data/plataforma (empresa_b).
    valor = os.environ.get("LICIGT_PAQUETES_DIRS")
    if valor:
        return [Path(p) for p in valor.split(os.pathsep) if p]
    return [RAIZ / "entregables" / "recuperacion", RAIZ / "data" / "plataforma"]


def _del_paquete(tenant_id: str, doc_id: str) -> bytes | None:
    for carpeta in _carpetas():
        paquete = carpeta / f"{tenant_id}.zip"
        if not paquete.is_file():
            continue
        with zipfile.ZipFile(paquete) as z:
            try:
                return z.read(f"originales/{doc_id}.pdf")
            except KeyError:
                continue
    return None


def leer_original(ctx, evento_id, doc_id, *, abrir) -> bytes | None:
    """El PDF, o None si no existe o no es de la empresa: quien llama no distingue ambos casos.

    abrir devuelve (conexión, sesión por empresa del rol 2); la ruta del archivo se arma solo
    con el doc_id hexadecimal y la empresa de la sesión, nunca con texto del usuario."""
    if not (isinstance(doc_id, str) and DOC_ID.fullmatch(doc_id) and TENANT_ID.fullmatch(ctx.tenant_id)):
        return None
    conn, sesion = abrir()
    try:
        with conn.transaction():
            sesion(conn, ctx)
            fila = conn.execute("SELECT 1 FROM documentos WHERE tenant_id = %s AND evento_id = %s AND doc_id = %s",
                                (ctx.tenant_id, evento_id, doc_id)).fetchone()
    finally:
        conn.close()
    return _del_paquete(ctx.tenant_id, doc_id) if fila else None
