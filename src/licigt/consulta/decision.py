"""Tabla de decisión ordenada: JEV juzga y el código decide."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .entrada import JuiciosEntrada
from .enrutador import Clasificacion
from .esquemas import NombreHerramienta, TEXTO_ACLARACION, TEXTO_ACLARACION_FECHA
from .preguntas_jev import Umbrales


class Siguiente(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    accion: Literal["abstener", "aclarar", "usar_herramienta"]
    motivo: Literal["longitud_invalida", "inyeccion", "fuera_de_alcance", "sin_herramienta", "no_especifica", "ok"]
    herramienta: NombreHerramienta | None = None
    pregunta_aclaratoria: str | None = None
    # Herramienta que eligió JEV cuando su probabilidad no alcanzó choice_min y se usó la de las reglas.
    herramienta_jev_sustituida: NombreHerramienta | None = None


def decidir(juicios: JuiciosEntrada, clasificacion: Clasificacion,
            umbrales: Umbrales = Umbrales()) -> Siguiente:
    if not juicios.longitud_valida:
        return Siguiente(accion="abstener", motivo="longitud_invalida")
    if juicios.inyeccion:
        return Siguiente(accion="abstener", motivo="inyeccion")
    if juicios.fuera_de_alcance:
        return Siguiente(accion="abstener", motivo="fuera_de_alcance")
    if (clasificacion.variante == "jev" and clasificacion.prob_aplica is not None
            and clasificacion.prob_aplica < umbrales.noul_no):
        return Siguiente(accion="abstener", motivo="sin_herramienta")
    if clasificacion.herramienta is None:
        return Siguiente(accion="abstener", motivo="sin_herramienta")
    if not juicios.especifica:
        return Siguiente(accion="aclarar", motivo="no_especifica",
                         pregunta_aclaratoria=TEXTO_ACLARACION_FECHA if juicios.menciona_fecha else TEXTO_ACLARACION)
    herramienta, sustituida = clasificacion.herramienta, None
    if (clasificacion.variante == "jev" and clasificacion.prob_herramienta is not None
            and clasificacion.prob_herramienta < umbrales.choice_min):
        herramienta, sustituida = juicios.herramienta_reglas, clasificacion.herramienta
    return Siguiente(accion="usar_herramienta", motivo="ok", herramienta=herramienta,
                     herramienta_jev_sustituida=sustituida)
