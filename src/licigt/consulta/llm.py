"""Generador compatible con OpenAI, con importación diferida y errores sin contenido remoto."""

from pathlib import Path
from urllib.parse import urlsplit

from .config import ConfiguracionLlm, obtener_configuracion_llm

HOSTS_LOCALES = {"127.0.0.1", "localhost"}
# Modo estricto de OpenAI: https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas
# lista minItems, maxItems y enum, pero no minLength ni maxLength; documenta minimum y maximum solo para "number", no para "integer".
# Sin verificar en integer no se envían; el validador local las aplica igual.
PALABRAS_NO_ADMITIDAS = ("minLength", "maxLength", "minimum", "maximum")


def _esquema_openai(nodo):
    if isinstance(nodo, dict):
        return {k: _esquema_openai(v) for k, v in nodo.items() if k not in PALABRAS_NO_ADMITIDAS}
    if isinstance(nodo, list):
        return [_esquema_openai(v) for v in nodo]
    return nodo


def _destino_seguro(config: ConfiguracionLlm) -> bool:
    partes = urlsplit(config.url)
    if config.perfil == "openai":
        if partes.scheme != "https" or partes.hostname != "api.openai.com":
            return False
        raiz = Path("keys").resolve()
        return config.archivo_clave.resolve().is_relative_to(raiz)
    return partes.scheme == "https" or (partes.scheme == "http" and partes.hostname in HOSTS_LOCALES)


class FallaGenerador(Exception):
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


class ClienteGeneradorOpenAI:
    def __init__(self, config: ConfiguracionLlm | None = None):
        self.config = config or obtener_configuracion_llm()
        self.perfil = self.config.perfil
        self.modelo_generador = self.config.modelo
        # Acumulado del `usage` que devuelve el servidor; quien mide toma la diferencia entre dos lecturas.
        self.uso = {"llamadas": 0, "tokens_entrada": 0, "tokens_salida": 0}
        if not _destino_seguro(self.config):
            raise FallaGenerador("config_insegura")
        try:
            from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
        except ImportError:
            raise FallaGenerador("sdk_no_disponible") from None
        self._tiempo, self._conexion, self._api = APITimeoutError, APIConnectionError, APIStatusError
        clave = "local-sin-clave"
        if self.perfil == "openai":
            try:
                clave = self.config.archivo_clave.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
                raise FallaGenerador("clave_no_disponible") from None
            if not clave:
                raise FallaGenerador("clave_no_disponible")
        try:
            self._cliente = OpenAI(api_key=clave, base_url=self.config.url,
                                   timeout=self.config.tiempo_espera, max_retries=0)
        except Exception:
            raise FallaGenerador("api") from None

    def generar(self, mensajes: list[dict], esquema: dict, semilla_extra: int = 0, *,
                max_tokens: int | None = None, tiempo_espera: float | None = None) -> str:
        """semilla_extra > 0 marca la regeneración: suma a la semilla y sube la temperatura para no repetir la salida.

        max_tokens sustituye al tope de la configuración (el orquestador pasa el de cada herramienta);
        tiempo_espera solo puede acortar la espera configurada, nunca alargarla."""
        if self.perfil == "openai":
            esquema = _esquema_openai(esquema)
        argumentos = dict(model=self.config.modelo, messages=mensajes,
                          temperature=self.config.temperatura_regeneracion if semilla_extra else 0,
                          seed=self.config.semilla + semilla_extra, max_tokens=max_tokens or self.config.max_tokens,
                          response_format={"type": "json_schema", "json_schema": {
                              "name": "salida_licigt", "schema": esquema, "strict": True}})
        if tiempo_espera is not None:
            argumentos["timeout"] = min(tiempo_espera, self.config.tiempo_espera)
        if self.perfil == "local":
            argumentos["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        try:
            respuesta = self._cliente.chat.completions.create(**argumentos)
        except (self._tiempo, TimeoutError):
            raise FallaGenerador("tiempo_agotado") from None
        except self._conexion:
            raise FallaGenerador("servicio_no_disponible") from None
        except self._api:
            raise FallaGenerador("api") from None
        except Exception:
            raise FallaGenerador("api") from None
        self._contar_uso(respuesta)
        try:
            # Con finish_reason "length" el JSON llega incompleto: es un error propio, no un json_invalido del modelo.
            if getattr(respuesta.choices[0], "finish_reason", None) == "length":
                raise FallaGenerador("respuesta_cortada")
            mensaje = respuesta.choices[0].message
            contenido = mensaje.content
            if getattr(mensaje, "refusal", None) or not isinstance(contenido, str) or not contenido.strip():
                raise ValueError
        except (AttributeError, IndexError, TypeError, ValueError):
            raise FallaGenerador("respuesta_vacia") from None
        modelo = getattr(respuesta, "model", None)
        if isinstance(modelo, str) and modelo:
            self.modelo_generador = modelo
        return contenido

    def _contar_uso(self, respuesta):
        uso = getattr(respuesta, "usage", None)
        self.uso["llamadas"] += 1
        for campo, atributo in (("tokens_entrada", "prompt_tokens"), ("tokens_salida", "completion_tokens")):
            valor = getattr(uso, atributo, 0)
            self.uso[campo] += valor if isinstance(valor, int) else 0

    def cerrar(self):
        self._cliente.close()
