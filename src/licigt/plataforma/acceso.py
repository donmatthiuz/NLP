"""Dependencias de FastAPI: la sesión sale solo de la cookie verificada; el rol se exige aquí."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from .usuarios import cargar
from .sesion import NOMBRE_COOKIE, Sesion, SesionNoConfigurada, leer_clave, verificar


def verificar_sesion(request: Request) -> Sesion:
    """Cookie válida y usuario que sigue existiendo con el mismo tenant_id y rol; si no, 401 (503 sin clave)."""
    try:
        clave = leer_clave()
    except SesionNoConfigurada:
        raise HTTPException(503, detail={"codigo": "sesion_no_configurada"}) from None
    valor = request.cookies.get(NOMBRE_COOKIE)
    sesion = verificar(valor, clave) if valor else None
    if sesion is None:
        raise HTTPException(401, detail={"codigo": "no_autenticado"})
    # Sin estado en el servidor, pero el archivo de usuarios manda: un usuario quitado o con otro rol pierde la sesión.
    registro = cargar().get(sesion.usuario)
    if not (isinstance(registro, dict) and registro.get("tenant_id") == sesion.tenant_id
            and registro.get("rol") == sesion.rol):
        raise HTTPException(401, detail={"codigo": "no_autenticado"})
    return sesion


def sesion_actual(request: Request) -> Sesion:
    return verificar_sesion(request)


def exigir_analista(sesion: Annotated[Sesion, Depends(sesion_actual)]) -> Sesion:
    if sesion.rol != "analista":
        raise HTTPException(403, detail={"codigo": "sin_permiso"})
    return sesion
