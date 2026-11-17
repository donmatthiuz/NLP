"""Configuración validada del enrutador, leída una vez al solicitarla."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ID exacto: https://docs.typesafe.ai/models (consulta del 16 de noviembre de 2026).
MODELO_JEV = "jev-1.14.0"
VARIABLES = {
    "enrutador": "LICIGT_ENRUTADOR", "modelo": "LICIGT_JEV_MODELO",
    "archivo_clave": "LICIGT_JEV_API_KEY_FILE", "reintentos": "LICIGT_JEV_REINTENTOS",
    "tiempo_espera": "LICIGT_JEV_TIEMPO_ESPERA", "espera_reintento": "LICIGT_JEV_ESPERA_REINTENTO",
    "max_solicitudes_seg": "LICIGT_JEV_MAX_SOLICITUDES_SEG",
    "espera_frecuencia": "LICIGT_JEV_ESPERA_FRECUENCIA",
}


class Configuracion(BaseModel):
    """Frecuencia local simulada; los límites reales se consultan en TypeSafe."""
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    enrutador: Literal["reglas", "jev", "llm"] = "reglas"
    modelo: str = Field(default=MODELO_JEV, pattern=r"^jev-\d+\.\d+\.\d+$")
    archivo_clave: Path = Path("keys/jev/api.key")
    reintentos: int = Field(default=2, ge=0)
    tiempo_espera: float = Field(default=5, gt=0)
    espera_reintento: float = Field(default=5, ge=0)
    max_solicitudes_seg: float = Field(default=5, gt=0)
    espera_frecuencia: float = Field(default=5, ge=0)


@lru_cache(maxsize=1)
def obtener_configuracion() -> Configuracion:
    return Configuracion(**{campo: os.environ[variable] for campo, variable in VARIABLES.items()
                            if variable in os.environ})


class ConfiguracionLlm(BaseModel):
    """Perfiles del generador; la llave se lee únicamente al crear el cliente remoto."""
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    perfil: Literal["local", "openai"] = "local"
    url: str = Field(default="http://127.0.0.1:8080/v1", pattern=r"^https?://\S+$")
    modelo: str = Field(default="qwen3.5-9b", min_length=1)
    archivo_clave: Path = Path("keys/llm/openai.key")
    tiempo_espera: float = Field(default=20, gt=0)
    max_tokens: int = Field(default=3072, gt=0)
    semilla: int = Field(default=42, ge=-(2**63), le=2**63 - 1)
    # Solo la regeneración: a temperatura 0 la semilla no influye y la salida se repite byte a byte.
    temperatura_regeneracion: float = Field(default=0.3, ge=0, le=2)
    max_caracteres_evidencia: int = Field(default=36000, gt=0)

    @model_validator(mode="before")
    @classmethod
    def aplicar_perfil(cls, datos):
        if isinstance(datos, dict) and datos.get("perfil") == "openai":
            return {"url": "https://api.openai.com/v1", "modelo": "gpt-4.1-mini", **datos}
        return datos


VARIABLES_LLM = {
    "perfil": "LICIGT_LLM", "url": "LICIGT_LLM_URL", "modelo": "LICIGT_LLM_MODELO",
    "archivo_clave": "LICIGT_LLM_API_KEY_FILE", "tiempo_espera": "LICIGT_LLM_TIEMPO_ESPERA",
    "max_tokens": "LICIGT_LLM_MAX_TOKENS", "semilla": "LICIGT_LLM_SEMILLA",
    "temperatura_regeneracion": "LICIGT_LLM_TEMPERATURA_REGENERACION",
    "max_caracteres_evidencia": "LICIGT_LLM_MAX_CARACTERES_EVIDENCIA",
}


@lru_cache(maxsize=1)
def obtener_configuracion_llm() -> ConfiguracionLlm:
    return ConfiguracionLlm(**{campo: os.environ[variable] for campo, variable in VARIABLES_LLM.items()
                               if variable in os.environ})
