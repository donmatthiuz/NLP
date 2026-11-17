"""Adaptador de desarrollo, reemplazable por la API del rol 4; sin autenticación."""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from .enrutador import crear_enrutador
from .esquemas import RespuestaEstructurada
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


@lru_cache(maxsize=None)
def obtener_generador():
    return ClienteGeneradorOpenAI()


def contexto_demo():
    from licigt.recuperacion.busqueda import Contexto
    return Contexto(tenant_id="empresa_demo", usuario="demo")


def _auditar(evento):
    # Solo metadatos: sin texto de PDF, de la pregunta ni de la respuesta.
    registro.info("consulta evento=%s herramienta=%s abstained=%s validacion=%s error=%s",
                  evento["evento_id"], evento["herramienta"], evento["abstained"],
                  evento["validacion"], evento["error"])


app = FastAPI(title="LiciGT consulta (demo)")


@app.middleware("http")
async def cabecera_demo(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers[CABECERA_DEMO] = "ninguna-demo"
    return respuesta


@app.post("/api/eventos/{evento_id}/consultas", response_model=RespuestaEstructurada)
def consultar_evento(
    evento_id: str,
    entrada: ConsultaEntrada,
    ctx: Annotated[object, Depends(contexto_demo)],
    enrutador: Annotated[object, Depends(obtener_enrutador)],
    recuperador: Annotated[object, Depends(obtener_recuperador)],
    generador: Annotated[object, Depends(obtener_generador)],
):
    return consultar(ctx, evento_id, entrada.pregunta, enrutador=enrutador,
                     recuperador=recuperador, generador=generador, auditar=_auditar)
