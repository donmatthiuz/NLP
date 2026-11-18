"""API de consulta: sesión por cookie firmada, rol y auditoría de la plataforma (rol 4)."""

import logging
import math
import os
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enrutador import crear_enrutador
from .esquemas import Categoria, RespuestaEstructurada
from .lista import Estado, ItemLista, ItemPropuesto, PropuestaLista, proponer_lista
from .lista_escritura import (
    Confirmacion, FallaLista, RepositorioMemoria, cambiar_estado, guardar_items, listar,
)
from .jev import ClienteJevSdk, FallaJev
from .llm import ClienteGeneradorOpenAI
from .orquestador import consultar
from licigt.plataforma import auditoria, originales, usuarios
from licigt.plataforma.acceso import exigir_analista, sesion_actual, verificar_sesion
from licigt.plataforma.sesion import NOMBRE_COOKIE, Sesion, SesionNoConfigurada, emitir, leer_clave

registro = logging.getLogger("licigt.consulta.api")


class ConsultaEntrada(BaseModel):
    """Cuerpo de la consulta: nunca acepta tenant_id ni otros campos."""
    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(min_length=1, max_length=500)


@lru_cache(maxsize=None)
def obtener_enrutador():
    return crear_enrutador()


def obtener_recuperador():
    # Importación tardía: busqueda arrastra psycopg y los modelos, que las pruebas no necesitan.
    from licigt.recuperacion import busqueda
    return busqueda


class _ConConfirmacion(BaseModel):
    """Escritura: sin confirmado true (booleano estricto) la petición no pasa de 422."""
    model_config = ConfigDict(extra="forbid")

    confirmado: Literal[True]

    @field_validator("confirmado", mode="before")
    @classmethod
    def solo_true(cls, valor):
        if valor is not True:
            raise ValueError("La confirmación debe ser true")
        return valor


class PropuestaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoria: Categoria | None = None


class DocumentoEvento(BaseModel):
    """Un documento del evento con su cobertura; sin texto del PDF."""
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    tipo_documento: str
    version_oficial: str | None
    version_ingesta: int
    estado: str
    paginas_total: int | None
    paginas_no_indexadas: list[int]
    advertencias: list[str]


class DocumentosEvento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evento_id: str
    documentos: list[DocumentoEvento]


class GuardarEntrada(_ConConfirmacion):
    items: list[ItemPropuesto]


class CambioEstadoEntrada(_ConConfirmacion):
    estado_anterior: Estado
    estado_nuevo: Estado


# Sin texto de documentos en el detalle: solo el código de la falla.
ESTADO_HTTP = {"item_no_encontrado": 404, "estado_desactualizado": 409}


@lru_cache(maxsize=None)
def obtener_repositorio():
    if os.environ.get("LICIGT_LISTA") == "postgres":
        # Importación tardía: arrastra psycopg, que las pruebas no necesitan.
        from licigt.recuperacion.indice import conectar
        from .lista_sql import RepositorioPostgres
        return RepositorioPostgres(conectar)
    return RepositorioMemoria()


@lru_cache(maxsize=None)
def obtener_lector():
    # Los fragmentos viven en el índice del rol 2 con o sin lista en Postgres: la cita se revalida siempre contra ellos.
    from licigt.recuperacion.indice import conectar
    from .lista_sql import LectorFragmentosPostgres
    return LectorFragmentosPostgres(conectar)


@lru_cache(maxsize=None)
def obtener_generador():
    return ClienteGeneradorOpenAI()


@lru_cache(maxsize=None)
def obtener_cliente_jev():
    """JEV verifica las fechas de la propuesta; sin SDK o sin llave la propuesta sigue con las fechas sin verificar."""
    try:
        return ClienteJevSdk()
    except FallaJev:
        return None


def contexto_acceso(sesion: Annotated[Sesion, Depends(sesion_actual)]):
    """El contexto del rol 2 sale solo de la cookie verificada; el rol se comprueba en la API."""
    from licigt.recuperacion.busqueda import Contexto
    return Contexto(tenant_id=sesion.tenant_id, usuario=sesion.usuario)


def _abrir_conexion_rol2():
    # Importación tardía: arrastra psycopg. Devuelve la conexión y la sesión por empresa (RLS) del rol 2.
    from licigt.recuperacion import busqueda
    from licigt.recuperacion.indice import conectar
    return conectar(), busqueda._sesion


def resolver_evento(evento_id: Annotated[str, Path()], ctx: Annotated[object, Depends(contexto_acceso)]) -> str:
    """Traduce el valor de la ruta (evento_id o numero_evento) al evento_id interno, solo de la empresa de la sesión."""
    from licigt.recuperacion import busqueda
    interno = busqueda.resolver_evento(ctx, evento_id)
    if interno is None:
        raise HTTPException(404, detail={"codigo": "evento_no_encontrado"})
    return interno


EventoInterno = Annotated[str, Depends(resolver_evento)]


def _auditar(evento):
    # Solo metadatos: sin texto de PDF, de la pregunta ni de la respuesta.
    auditoria.registrar_consulta(evento)
    registro.info("consulta evento=%s herramienta=%s abstained=%s validacion=%s error=%s",
                  evento["evento_id"], evento["herramienta"], evento["abstained"],
                  evento["validacion"], evento["error"])


def _auditar_propuesta(evento):
    # La propuesta emite el evento completo del orquestador; la auditoría conserva solo los campos del contrato.
    auditoria.registrar_consulta(evento)
    registro.info("lista %s", {"accion": "proponer_lista", "evento_id": evento.get("evento_id"), "error": evento.get("error")})


def _auditar_lista(evento):
    # Metadatos de la operación: sin citas ni texto de fragmentos.
    auditoria.registrar_lista(evento)
    registro.info("lista %s", {k: v for k, v in evento.items() if k in ("accion", "evento_id", "item_ids", "error")})


def obtener_lector_originales():
    # Se resuelve _abrir_conexion_rol2 al llamar, para que las pruebas puedan sustituirla.
    return lambda ctx, evento_id, doc_id: originales.leer_original(ctx, evento_id, doc_id, abrir=_abrir_conexion_rol2)


app = FastAPI(title="LiciGT API")

DURACION_HORAS = 8


class CredencialesEntrada(BaseModel):
    """Cuerpo del inicio de sesión: nunca acepta tenant_id ni otros campos."""
    model_config = ConfigDict(extra="forbid")

    usuario: str = Field(min_length=1, max_length=64)
    contrasena: str = Field(min_length=1, max_length=256)


class SesionSalida(BaseModel):
    usuario: str
    tenant_id: str
    rol: str


def _horas_de_sesion() -> float:
    """Horas de vida de la cookie, en (0, 24]; un valor fuera de rango, nan o inf vuelve al valor por defecto."""
    valor = os.environ.get("LICIGT_SESION_HORAS")
    if valor is None:
        return DURACION_HORAS
    try:
        horas = float(valor)
    except ValueError:
        horas = math.nan
    if not (math.isfinite(horas) and 0 < horas <= 24):
        registro.warning("LICIGT_SESION_HORAS fuera de (0, 24]: se usan %s horas", DURACION_HORAS)
        return DURACION_HORAS
    return horas


def _origenes_permitidos() -> set[str]:
    """Orígenes que pueden escribir: por defecto la API y Vite en local; LICIGT_ORIGENES_PERMITIDOS los reemplaza."""
    configurado = os.environ.get("LICIGT_ORIGENES_PERMITIDOS")
    if configurado:
        return {o.strip().rstrip("/") for o in configurado.split(",") if o.strip()}
    puertos = (os.environ.get("LICIGT_API_PUERTO") or "8000", "5173")
    return {f"http://{host}:{puerto}" for host in ("127.0.0.1", "localhost") for puerto in puertos}


def _origen_ajeno(request: Request) -> bool:
    """Defensa en profundidad además de SameSite=Strict: Origin o Referer presentes y no permitidos."""
    permitidos = _origenes_permitidos()
    origen = request.headers.get("origin")
    if origen is not None:
        return origen.rstrip("/") not in permitidos
    referer = request.headers.get("referer")
    if referer is not None:
        partes = urlsplit(referer)
        return f"{partes.scheme}://{partes.netloc}" not in permitidos
    return False


@app.middleware("http")
async def proteger_api(request: Request, call_next):
    """Antes de leer el cuerpo: origen permitido (403) y sesión válida (401); solo /api/sesion queda abierta."""
    ruta = request.url.path
    if ruta.startswith("/api"):
        if request.method in ("POST", "PATCH", "PUT", "DELETE") and _origen_ajeno(request):
            return JSONResponse({"detail": {"codigo": "origen_no_permitido"}}, status_code=403)
        if ruta.rstrip("/") != "/api/sesion":
            try:
                verificar_sesion(request)
            except HTTPException as falla:
                return JSONResponse({"detail": falla.detail}, status_code=falla.status_code)
    return await call_next(request)


@app.post("/api/sesion", status_code=204)
def iniciar_sesion(entrada: CredencialesEntrada):
    try:
        clave = leer_clave()
    except SesionNoConfigurada:
        raise HTTPException(503, detail={"codigo": "sesion_no_configurada"}) from None
    usuario = usuarios.autenticar(entrada.usuario, entrada.contrasena)
    if usuario is None:
        auditoria.registrar_login_fallido(entrada.usuario)
        # Mensaje genérico: no distingue usuario inexistente de contraseña mala.
        raise HTTPException(401, detail={"codigo": "credenciales_invalidas"})
    horas = _horas_de_sesion()
    respuesta = Response(status_code=204)
    # HttpOnly: el JavaScript no la lee. Strict: no viaja en peticiones iniciadas desde otro sitio.
    respuesta.set_cookie(NOMBRE_COOKIE, emitir(clave, usuario.usuario, usuario.tenant_id, usuario.rol, horas),
                         max_age=int(horas * 3600), httponly=True, samesite="strict", path="/")
    auditoria.registrar("login", "ok", usuario=usuario.usuario, tenant_id=usuario.tenant_id)
    return respuesta


@app.delete("/api/sesion", status_code=204)
def cerrar_sesion():
    respuesta = Response(status_code=204)
    respuesta.delete_cookie(NOMBRE_COOKIE, httponly=True, samesite="strict", path="/")
    return respuesta


@app.get("/api/sesion", response_model=SesionSalida)
def ver_sesion(sesion: Annotated[Sesion, Depends(sesion_actual)]):
    return SesionSalida(usuario=sesion.usuario, tenant_id=sesion.tenant_id, rol=sesion.rol)


@app.post("/api/eventos/{evento_id}/consultas", response_model=RespuestaEstructurada)
def consultar_evento(
    evento_id: EventoInterno,
    entrada: ConsultaEntrada,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
    enrutador: Annotated[object, Depends(obtener_enrutador)],
    recuperador: Annotated[object, Depends(obtener_recuperador)],
    generador: Annotated[object, Depends(obtener_generador)],
):
    respuesta = consultar(ctx, evento_id, entrada.pregunta, enrutador=enrutador,
                          recuperador=recuperador, generador=generador, auditar=_auditar)
    # El orquestador trabaja con el id interno; quien llama recibe el valor que pidió en la ruta.
    return respuesta.model_copy(update={"evento_id": request.path_params["evento_id"]})


@app.get("/api/eventos/{evento_id}/documentos", response_model=DocumentosEvento)
def documentos_del_evento(
    evento_id: EventoInterno,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
):
    """Documentos incorporados al evento y qué información falta; solo lectura de la tabla documentos, por empresa."""
    conn, sesion = _abrir_conexion_rol2()
    try:
        with conn.transaction():
            sesion(conn, ctx)
            filas = conn.execute(
                """SELECT doc_id, tipo_documento, identificador_version_oficial, version_ingesta, status,
                          paginas_no_indexadas, inventario->'cobertura'->>'paginas_total', inventario->'warnings'
                   FROM documentos WHERE tenant_id = %s AND evento_id = %s
                   ORDER BY CASE tipo_documento WHEN 'bases' THEN 0 ELSE 1 END, tipo_documento, version_ingesta""",
                (ctx.tenant_id, evento_id)).fetchall()
    finally:
        conn.close()
    return DocumentosEvento(evento_id=request.path_params["evento_id"], documentos=[
        DocumentoEvento(doc_id=d, tipo_documento=t, version_oficial=o, version_ingesta=v, estado=e,
                        paginas_total=int(total) if total is not None else None,
                        paginas_no_indexadas=list(sin_indexar or []), advertencias=list(avisos or []))
        for d, t, o, v, e, sin_indexar, total, avisos in filas])


def _con_evento(modelo, pedido: str):
    """Quien llama recibe el valor que pidió en la ruta; el repositorio y el orquestador siguen con el id interno."""
    return modelo.model_copy(update={"evento_id": pedido})


def _falla_http(falla: FallaLista) -> HTTPException:
    return HTTPException(ESTADO_HTTP.get(falla.codigo, 422), detail={"codigo": falla.codigo})


@app.post("/api/eventos/{evento_id}/lista/propuesta", response_model=PropuestaLista,
          dependencies=[Depends(exigir_analista)])
def proponer(
    evento_id: EventoInterno,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
    recuperador: Annotated[object, Depends(obtener_recuperador)],
    cliente_jev: Annotated[object, Depends(obtener_cliente_jev)],
    entrada: PropuestaEntrada | None = None,
):
    propuesta = proponer_lista(ctx, evento_id, entrada.categoria if entrada else None,
                               recuperador=recuperador, cliente_jev=cliente_jev, auditar=_auditar_propuesta)
    pedido = request.path_params["evento_id"]
    return propuesta.model_copy(update={"evento_id": pedido, "respuesta": _con_evento(propuesta.respuesta, pedido)})


@app.get("/api/eventos/{evento_id}/lista", response_model=list[ItemLista])
def ver_lista(
    evento_id: EventoInterno,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
):
    pedido = request.path_params["evento_id"]
    return [_con_evento(i, pedido) for i in listar(ctx, evento_id, repositorio=repositorio)]


@app.post("/api/eventos/{evento_id}/lista", response_model=list[ItemLista], dependencies=[Depends(exigir_analista)])
def guardar(
    evento_id: EventoInterno,
    entrada: GuardarEntrada,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
    lector: Annotated[object, Depends(obtener_lector)],
):
    try:
        guardados = guardar_items(ctx, evento_id, entrada.items, Confirmacion(confirmado=True),
                                  repositorio=repositorio, lector=lector, auditar=_auditar_lista)
        return [_con_evento(i, request.path_params["evento_id"]) for i in guardados]
    except FallaLista as falla:
        raise _falla_http(falla)


@app.patch("/api/eventos/{evento_id}/lista/{item_id}", response_model=ItemLista,
           dependencies=[Depends(exigir_analista)])
def cambiar(
    evento_id: EventoInterno,
    item_id: str,
    entrada: CambioEstadoEntrada,
    request: Request,
    ctx: Annotated[object, Depends(contexto_acceso)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
):
    try:
        item = cambiar_estado(ctx, item_id, entrada.estado_anterior, entrada.estado_nuevo,
                              Confirmacion(confirmado=True), repositorio=repositorio, auditar=_auditar_lista,
                              evento_id=evento_id)
        return _con_evento(item, request.path_params["evento_id"])
    except FallaLista as falla:
        raise _falla_http(falla)


@app.get("/api/eventos/{evento_id}/documentos/{doc_id}/original")
def original_del_documento(
    evento_id: EventoInterno,
    doc_id: str,
    ctx: Annotated[object, Depends(contexto_acceso)],
    lector: Annotated[object, Depends(obtener_lector_originales)],
):
    """PDF original de un documento del evento, solo de la empresa de la sesión; si no, 404 sin distinguir la causa."""
    # Segunda barrera: el lector también valida, pero un doc_id que no es un id de documento no llega a él.
    contenido = lector(ctx, evento_id, doc_id) if originales.DOC_ID.fullmatch(doc_id) else None
    auditoria.registrar("original", "ok" if contenido else "no_encontrado", usuario=ctx.usuario,
                        tenant_id=ctx.tenant_id, evento_id=evento_id)
    if contenido is None:
        raise HTTPException(404, detail={"codigo": "documento_no_encontrado"})
    return Response(contenido, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{doc_id}.pdf"', "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store"})
