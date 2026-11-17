"""Tabla de decisión ordenada: JEV juzga y el código decide."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .entrada import JuiciosEntrada
from .enrutador import Clasificacion
from .esquemas import NombreHerramienta, TEXTO_ACLARACION, TEXTO_ACLARACION_FECHA
from .preguntas_jev import CHOICE_MIN, NOUL_NO


class Siguiente(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    accion: Literal["abstener", "aclarar", "usar_herramienta"]
    motivo: Literal["longitud_invalida", "inyeccion", "fuera_de_alcance", "sin_herramienta", "no_especifica", "ok"]
    herramienta: NombreHerramienta | None = None
    pregunta_aclaratoria: str | None = None


def decidir(juicios: JuiciosEntrada, clasificacion: Clasificacion) -> Siguiente:
    if not juicios.longitud_valida:
        return Siguiente(accion="abstener", motivo="longitud_invalida")
    if juicios.inyeccion:
        return Siguiente(accion="abstener", motivo="inyeccion")
    if juicios.fuera_de_alcance:
        return Siguiente(accion="abstener", motivo="fuera_de_alcance")
    if (clasificacion.variante == "jev" and clasificacion.prob_aplica is not None
            and clasificacion.prob_aplica < NOUL_NO):
        return Siguiente(accion="abstener", motivo="sin_herramienta")
    if clasificacion.herramienta is None:
        return Siguiente(accion="abstener", motivo="sin_herramienta")
    if not juicios.especifica:
        return Siguiente(accion="aclarar", motivo="no_especifica",
                         pregunta_aclaratoria=TEXTO_ACLARACION_FECHA if juicios.menciona_fecha else TEXTO_ACLARACION)
    herramienta = clasificacion.herramienta
    if (clasificacion.variante == "jev" and clasificacion.prob_herramienta is not None
            and clasificacion.prob_herramienta < CHOICE_MIN):
        herramienta = juicios.herramienta_reglas
    return Siguiente(accion="usar_herramienta", motivo="ok", herramienta=herramienta)
