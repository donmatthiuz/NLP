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

    def generar(self, mensajes: list[dict], esquema: dict) -> str:
        if self.perfil == "openai":
            esquema = _esquema_openai(esquema)
        argumentos = dict(model=self.config.modelo, messages=mensajes, temperature=0,
                          seed=self.config.semilla, max_tokens=self.config.max_tokens,
                          response_format={"type": "json_schema", "json_schema": {
                              "name": "salida_licigt", "schema": esquema, "strict": True}})
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
        try:
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

    def cerrar(self):
        self._cliente.close()
