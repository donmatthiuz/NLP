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
    # Medido sin recorte (18-nov, espera 60 s, max_tokens 3072, 71 preguntas de desarrollo, 91 llamadas):
    # salidas de buscar_documentos p50 163, p99 1137, máx 1137 tokens; comparar_versiones máx 801 (solo 2 llamadas);
    # extraer_requisitos p50 796, p99 1781, máx 1781 (las válidas, máx 1114). Con ~79 tok/s: 1536 tok = 19,4 s y 2048 tok = 25,9 s.
    # La espera cubre 2048 tok más hasta ~6 s de prefill. Ojo: 11 de 54 llamadas de extraer_requisitos se cortaron entre 290 y 920 tokens
    # porque prompt (~11,5 k) + salida llenó el contexto del slot (12 288): ahí manda el contexto, no max_tokens.
    tiempo_espera: float = Field(default=40, gt=0)
    max_tokens: int = Field(default=1536, gt=0)
    max_tokens_requisitos: int = Field(default=2048, gt=0)
    # Tope de tiempo de la solicitud entera: con él gastado no se regenera.
    presupuesto_segundos: float = Field(default=15, gt=0, allow_inf_nan=False)
    # Duración estimada de una regeneración: p75 de las segundas llamadas medidas solo con preguntas de desarrollo
    # (casos_desarrollo, casos_calibracion y CASOS_ADICIONALES; n=32: p50 7,9, p75 10,1, p90 11,0, máx 16,3 s).
    # Se usa el menor entre este valor y lo que tardó el primer intento.
    estimacion_regeneracion_segundos: float = Field(default=10, gt=0, allow_inf_nan=False)
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
    "max_tokens": "LICIGT_LLM_MAX_TOKENS", "max_tokens_requisitos": "LICIGT_LLM_MAX_TOKENS_REQUISITOS", "semilla": "LICIGT_LLM_SEMILLA",
    "temperatura_regeneracion": "LICIGT_LLM_TEMPERATURA_REGENERACION",
    "max_caracteres_evidencia": "LICIGT_LLM_MAX_CARACTERES_EVIDENCIA",
    "presupuesto_segundos": "LICIGT_PRESUPUESTO_SEGUNDOS",
    "estimacion_regeneracion_segundos": "LICIGT_ESTIMACION_REGENERACION_SEGUNDOS",
}


@lru_cache(maxsize=1)
def obtener_configuracion_llm() -> ConfiguracionLlm:
    return ConfiguracionLlm(**{campo: os.environ[variable] for campo, variable in VARIABLES_LLM.items()
                               if variable in os.environ})
