"""Adaptador de desarrollo, reemplazable por la API del rol 4; sin autenticación."""

import logging
import os
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enrutador import crear_enrutador
from .esquemas import Categoria, RespuestaEstructurada
from .lista import Estado, ItemLista, ItemPropuesto, PropuestaLista, proponer_lista
from .lista_escritura import (
    Confirmacion, FallaLista, RepositorioMemoria, cambiar_estado, guardar_items, listar,
)
from .llm import ClienteGeneradorOpenAI
from .orquestador import consultar

CABECERA_DEMO = "X-LiciGT-Autenticacion"
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


def contexto_demo():
    from licigt.recuperacion.busqueda import Contexto
    return Contexto(tenant_id="empresa_demo", usuario="demo")


def _abrir_conexion_rol2():
    # Importación tardía: arrastra psycopg. Devuelve la conexión y la sesión por empresa (RLS) del rol 2.
    from licigt.recuperacion import busqueda
    from licigt.recuperacion.indice import conectar
    return conectar(), busqueda._sesion


def resolver_evento(evento_id: Annotated[str, Path()], ctx: Annotated[object, Depends(contexto_demo)]) -> str:
    """Traduce el valor de la ruta (evento_id o numero_evento) al evento_id interno, solo de la empresa de la sesión."""
    conn, sesion = _abrir_conexion_rol2()
    try:
        with conn.transaction():
            sesion(conn, ctx)
            fila = conn.execute("SELECT evento_id FROM documentos WHERE tenant_id = %s AND %s IN (evento_id, numero_evento)",
                                (ctx.tenant_id, evento_id)).fetchone()
    finally:
        conn.close()
    if not fila:
        raise HTTPException(404, detail={"codigo": "evento_no_encontrado"})
    return fila[0]


EventoInterno = Annotated[str, Depends(resolver_evento)]


def _auditar(evento):
    # Solo metadatos: sin texto de PDF, de la pregunta ni de la respuesta.
    registro.info("consulta evento=%s herramienta=%s abstained=%s validacion=%s error=%s",
                  evento["evento_id"], evento["herramienta"], evento["abstained"],
                  evento["validacion"], evento["error"])


def _auditar_lista(evento):
    # Metadatos de la operación: sin citas ni texto de fragmentos.
    registro.info("lista %s", {k: v for k, v in evento.items() if k in ("accion", "evento_id", "item_ids", "error")})


app = FastAPI(title="LiciGT consulta (demo)")


@app.middleware("http")
async def cabecera_demo(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers[CABECERA_DEMO] = "ninguna-demo"
    return respuesta


@app.post("/api/eventos/{evento_id}/consultas", response_model=RespuestaEstructurada)
def consultar_evento(
    evento_id: EventoInterno,
    entrada: ConsultaEntrada,
    ctx: Annotated[object, Depends(contexto_demo)],
    enrutador: Annotated[object, Depends(obtener_enrutador)],
    recuperador: Annotated[object, Depends(obtener_recuperador)],
    generador: Annotated[object, Depends(obtener_generador)],
):
    return consultar(ctx, evento_id, entrada.pregunta, enrutador=enrutador,
                     recuperador=recuperador, generador=generador, auditar=_auditar)


def _falla_http(falla: FallaLista) -> HTTPException:
    return HTTPException(ESTADO_HTTP.get(falla.codigo, 422), detail={"codigo": falla.codigo})


@app.post("/api/eventos/{evento_id}/lista/propuesta", response_model=PropuestaLista)
def proponer(
    evento_id: EventoInterno,
    ctx: Annotated[object, Depends(contexto_demo)],
    recuperador: Annotated[object, Depends(obtener_recuperador)],
    generador: Annotated[object, Depends(obtener_generador)],
    entrada: PropuestaEntrada | None = None,
):
    return proponer_lista(ctx, evento_id, entrada.categoria if entrada else None,
                          recuperador=recuperador, generador=generador, auditar=_auditar_lista)


@app.get("/api/eventos/{evento_id}/lista", response_model=list[ItemLista])
def ver_lista(
    evento_id: EventoInterno,
    ctx: Annotated[object, Depends(contexto_demo)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
):
    return listar(ctx, evento_id, repositorio=repositorio)


@app.post("/api/eventos/{evento_id}/lista", response_model=list[ItemLista])
def guardar(
    evento_id: EventoInterno,
    entrada: GuardarEntrada,
    ctx: Annotated[object, Depends(contexto_demo)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
    lector: Annotated[object, Depends(obtener_lector)],
):
    try:
        return guardar_items(ctx, evento_id, entrada.items, Confirmacion(confirmado=True),
                             repositorio=repositorio, lector=lector, auditar=_auditar_lista)
    except FallaLista as falla:
        raise _falla_http(falla)


@app.patch("/api/eventos/{evento_id}/lista/{item_id}", response_model=ItemLista)
def cambiar(
    evento_id: EventoInterno,
    item_id: str,
    entrada: CambioEstadoEntrada,
    ctx: Annotated[object, Depends(contexto_demo)],
    repositorio: Annotated[object, Depends(obtener_repositorio)],
):
    try:
        return cambiar_estado(ctx, item_id, entrada.estado_anterior, entrada.estado_nuevo,
                              Confirmacion(confirmado=True), repositorio=repositorio, auditar=_auditar_lista)
    except FallaLista as falla:
        raise _falla_http(falla)
