"""Variantes intercambiables de clasificación; la decisión vive en decision.py."""

import re
from copy import deepcopy
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from .config import Configuracion, obtener_configuracion
from .entrada import JuiciosEntrada, evaluar_entrada, normalizar
from .esquemas import NombreHerramienta
from .jev import ClienteJev, ClienteJevSdk, FallaJev, Probabilidad, validar_respuesta
from .preguntas_jev import NOUL_NO, NOUL_SI, PREGUNTAS_ENTRADA

PATRONES_COMPARACION = (r"\bcambi(?:o|os)\b", r"\bmodific\w*", r"\bdiferencia\w*",
                        r"\bversion\w*", r"\bantes y despues\b", r"\bvigente\w*")
PATRONES_REQUISITOS = (r"\brequisito\w*", r"\blista\w*", r"\b(?:fecha|plazo|hora)s?\b",
                       r"\bcronograma\b", r"\bcuando\b",
                       r"\bdocumentos\b.{0,50}\b(?:presentar|contener|plica)\b")


class Clasificacion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    herramienta: NombreHerramienta | None
    variante: Literal["reglas", "jev", "llm"]
    degradado: bool = False
    prob_herramienta: Probabilidad | None = None
    prob_aplica: Probabilidad | None = None
    modelo: str | None = None


class Enrutador(Protocol):
    def clasificar(self, pregunta: str) -> tuple[JuiciosEntrada, Clasificacion]: ...


class ClienteLlm(Protocol):
    """Dict con inyeccion, fuera_de_alcance, especifica y herramienta; se valida localmente."""
    def clasificar(self, pregunta: str) -> dict: ...


class JuiciosLlm(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inyeccion: bool
    fuera_de_alcance: bool
    especifica: bool
    herramienta: NombreHerramienta | None


class EnrutadorReglas:
    def clasificar(self, pregunta: str) -> tuple[JuiciosEntrada, Clasificacion]:
        juicios = evaluar_entrada(pregunta)
        herramienta = None
        if juicios.longitud_valida:
            texto = normalizar(pregunta)
            if any(re.search(p, texto) for p in PATRONES_COMPARACION):
                herramienta = "comparar_versiones"
            elif any(re.search(p, texto) for p in PATRONES_REQUISITOS):
                herramienta = "extraer_requisitos"
            else:
                herramienta = "buscar_documentos"
        return (juicios.model_copy(update={"herramienta_reglas": herramienta}),
                Clasificacion(herramienta=herramienta, variante="reglas"))


class EnrutadorJev:
    def __init__(self, cliente: ClienteJev | None = None, config: Configuracion | None = None):
        self.cliente, self.config = cliente, config

    def clasificar(self, pregunta: str) -> tuple[JuiciosEntrada, Clasificacion]:
        juicios, reglas = EnrutadorReglas().clasificar(pregunta)
        if not juicios.longitud_valida:
            return juicios, reglas
        preguntas = deepcopy(PREGUNTAS_ENTRADA)
        try:
            if self.cliente is None:
                self.cliente = ClienteJevSdk(self.config)
            respuesta = validar_respuesta(self.cliente.preguntar({"pregunta": pregunta}, preguntas), preguntas)
            datos = respuesta.respuestas
            eleccion = datos["herramienta"]
            clasificacion = Clasificacion(
                herramienta=eleccion["choice"], variante="jev", modelo=respuesta.modelo,
                prob_herramienta=eleccion["probabilities"][eleccion["choice"]],
                prob_aplica=datos["aplica"]["noul"])
            juicios = juicios.model_copy(update={
                "inyeccion": juicios.inyeccion or datos["inyeccion"]["noul"] >= NOUL_SI,
                "fuera_de_alcance": juicios.fuera_de_alcance or datos["fuera_de_alcance"]["noul"] >= NOUL_SI,
                "especifica": juicios.especifica and datos["concreta"]["noul"] >= NOUL_NO,
            })
            return juicios, clasificacion
        except (FallaJev, TimeoutError, ValidationError):
            return juicios, reglas.model_copy(update={"degradado": True})


class EnrutadorLlm:
    def __init__(self, cliente: ClienteLlm | None = None):
        self.cliente = cliente

    def clasificar(self, pregunta: str) -> tuple[JuiciosEntrada, Clasificacion]:
        juicios, reglas = EnrutadorReglas().clasificar(pregunta)
        if not juicios.longitud_valida:
            return juicios, reglas
        if self.cliente is None:
            return juicios, reglas.model_copy(update={"degradado": True})
        try:
            datos = JuiciosLlm.model_validate(self.cliente.clasificar(pregunta))
        except Exception:  # Frontera de un cliente externo todavía no elegido.
            return juicios, reglas.model_copy(update={"degradado": True})
        juicios = juicios.model_copy(update={
            "inyeccion": juicios.inyeccion or datos.inyeccion,
            "fuera_de_alcance": juicios.fuera_de_alcance or datos.fuera_de_alcance,
            "especifica": juicios.especifica and datos.especifica,
        })
        return juicios, Clasificacion(herramienta=datos.herramienta, variante="llm")


def crear_enrutador(config: Configuracion | None = None, *, cliente_jev=None, cliente_llm=None) -> Enrutador:
    config = config or obtener_configuracion()
    if config.enrutador == "jev":
        return EnrutadorJev(cliente_jev, config)
    if config.enrutador == "llm":
        return EnrutadorLlm(cliente_llm)
    return EnrutadorReglas()
