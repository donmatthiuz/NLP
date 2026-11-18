"""Adaptador de TypeSafe con fallas controladas y frecuencia local simulada."""

import math
import time
from threading import Lock
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .config import Configuracion, obtener_configuracion
from .esquemas import Entero, TextoNoVacio

Probabilidad = Annotated[float, Field(ge=0, le=1, strict=True, allow_inf_nan=False)]
ADAPTADOR_PROBABILIDAD = TypeAdapter(Probabilidad)


class FallaJev(Exception):
    """Código estable sin el contenido del error remoto."""
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


class RespuestaJev(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    respuestas: dict[str, dict]
    modelo: TextoNoVacio
    request_id: str | None
    tokens_entrada: Entero | None = Field(ge=0)
    tokens_salida: Entero | None = Field(ge=0)
    original: dict | None = None


class ClienteJev(Protocol):
    def preguntar(self, estado: dict, preguntas: dict) -> RespuestaJev: ...


def validar_respuesta(respuesta: RespuestaJev, preguntas: dict) -> RespuestaJev:
    """Comprueba todas las respuestas antes de interpretar algún juicio."""
    try:
        for nombre, pregunta in preguntas.items():
            dato = respuesta.respuestas[nombre]
            if dato["type"] != pregunta["type"]:
                raise ValueError("Tipo incorrecto")
            if pregunta["type"] == "noul":
                ADAPTADOR_PROBABILIDAD.validate_python(dato["noul"])
            elif pregunta["type"] == "choice":
                opciones = pregunta["criteria"]
                if dato["choice"] not in opciones or set(dato["probabilities"]) != set(opciones):
                    raise ValueError("Opciones incompletas")
                ADAPTADOR_PROBABILIDAD.validate_python(dato["confidence"])
                for probabilidad in dato["probabilities"].values():
                    ADAPTADOR_PROBABILIDAD.validate_python(probabilidad)
            else:
                raise ValueError("Tipo no soportado")
    except (AttributeError, KeyError, TypeError, ValueError):
        raise FallaJev("respuesta_incompleta") from None
    return respuesta


class LimitadorFrecuencia:
    """Cubeta con ráfaga inicial de una ficha por solicitud/segundo configurada."""
    def __init__(self, max_solicitudes_seg=5, espera_maxima=5, reloj=time.monotonic, dormir=time.sleep):
        if (not math.isfinite(max_solicitudes_seg) or max_solicitudes_seg <= 0
                or not math.isfinite(espera_maxima) or espera_maxima < 0):
            raise ValueError("Frecuencia y espera fuera de rango")
        self.tasa, self.espera_maxima = max_solicitudes_seg, espera_maxima
        self.capacidad = max(1, max_solicitudes_seg)
        self.fichas = self.capacidad
        self.reloj, self.dormir = reloj, dormir
        self.ultimo = reloj()
        self.cerrojo = Lock()

    def adquirir(self):
        limite = self.reloj() + self.espera_maxima
        espero = False
        while True:
            with self.cerrojo:
                ahora = self.reloj()
                if espero and ahora > limite:
                    raise FallaJev("limite_frecuencia")
                self.fichas = min(self.capacidad, self.fichas + max(0, ahora - self.ultimo) * self.tasa)
                self.ultimo = ahora
                if self.fichas >= 1:
                    self.fichas -= 1
                    return
                restante = limite - ahora
                if restante <= 0:
                    raise FallaJev("limite_frecuencia")
                espera = min((1 - self.fichas) / self.tasa, restante)
            self.dormir(espera)
            espero = True


class ClienteJevSdk:
    def __init__(self, config: Configuracion | None = None, limitador=None):
        config = config or obtener_configuracion()
        try:
            from typesafe_sdk import RetryPolicy, TypeSafeAPIError, TypeSafeClient, TypeSafeError
        except ImportError:
            raise FallaJev("sdk_no_disponible") from None
        self._error_api, self._error_sdk = TypeSafeAPIError, TypeSafeError
        try:
            clave = config.archivo_clave.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            raise FallaJev("clave_no_disponible") from None
        if not clave:
            raise FallaJev("clave_no_disponible")
        try:
            self._cliente = TypeSafeClient(
                api_key=clave, model=config.modelo, timeout=config.tiempo_espera,
                retry=RetryPolicy(max_retries=config.reintentos, timeout=config.tiempo_espera,
                                  backoff_max=config.espera_reintento))
        except TypeSafeError:
            raise FallaJev("sdk") from None
        self.limitador = limitador or LimitadorFrecuencia(config.max_solicitudes_seg,
                                                         config.espera_frecuencia)

    def preguntar(self, estado: dict, preguntas: dict) -> RespuestaJev:
        self.limitador.adquirir()
        try:
            resultado = self._cliente.system_one(state=estado, questions=preguntas)
        except TimeoutError:
            raise FallaJev("tiempo_agotado") from None
        except self._error_api:
            raise FallaJev("api") from None
        except self._error_sdk:
            raise FallaJev("sdk") from None
        try:
            respuesta = RespuestaJev(
                respuestas={nombre: dato.model_dump(mode="json")
                            for nombre, dato in resultado.answers.items()},
                modelo=resultado.model, request_id=resultado.request_id,
                tokens_entrada=resultado.usage.input_tokens, tokens_salida=resultado.usage.output_tokens,
                original=resultado.raw_http_response.json())
        except (AttributeError, TypeError, ValueError):
            raise FallaJev("respuesta_incompleta") from None
        return validar_respuesta(respuesta, preguntas)

    def cerrar(self):
        self._cliente.close()
