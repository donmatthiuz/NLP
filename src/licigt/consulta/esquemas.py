"""Contratos de salida y parámetros de las herramientas de consulta."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

NombreHerramienta = Literal["buscar_documentos", "extraer_requisitos", "comparar_versiones"]
TipoDocumento = Literal["bases", "anexo", "aclaracion", "modificacion"]
Categoria = Literal["administrativa", "legal", "tecnica", "financiera"]
TEXTO_ABSTENCION = "No hay información suficiente en los documentos para responder"

TextoNoVacio = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
TextoRecortado = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
# Estricto: la salida del modelo no puede colar true como 1 ni "7" como 7.
Entero = Annotated[int, Field(strict=True)]


class Fuente(BaseModel):
    """Cita con página y versiones; source recibe la URL o, si falta, doc_id."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: TextoNoVacio
    source: TextoNoVacio
    page: Entero = Field(ge=1)
    page_end: Entero | None
    chunk_id: TextoNoVacio
    version_ingesta: Entero = Field(ge=0)
    version_oficial: str | None
    cita: TextoRecortado

    @model_validator(mode="after")
    def validar_paginas(self) -> "Fuente":
        if self.page_end is not None and self.page_end < self.page:
            raise ValueError("La página final no puede ser menor que la inicial")
        return self


class RespuestaEstructurada(BaseModel):
    """Respuesta con fuentes o abstención explícita."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: TextoNoVacio
    sources: list[Fuente]
    abstained: StrictBool
    tool_used: NombreHerramienta | None
    needs_human_review: StrictBool
    evento_id: TextoNoVacio
    coverage_status: Literal["parcial", "sin_faltantes_detectados"]
    warnings: list[TextoNoVacio] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_evidencia(self) -> "RespuestaEstructurada":
        if not self.abstained and not self.sources:
            raise ValueError("Una respuesta sin abstención requiere al menos una fuente")
        if self.abstained and self.answer != TEXTO_ABSTENCION:
            raise ValueError("La abstención requiere el texto fijo del contrato")
        return self


class BuscarDocumentosParams(BaseModel):
    """La herramienta filtra el tipo sobre resultados: buscar() del rol 2 no lo admite."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: TextoRecortado
    evento_id: TextoNoVacio
    tipo_documento: TipoDocumento | None = None
    k: Entero = Field(default=5, ge=1, le=10)


class ExtraerRequisitosParams(BaseModel):
    """Evento y categoría opcional de los requisitos."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    evento_id: TextoNoVacio
    categoria: Categoria | None = None


class CompararVersionesParams(BaseModel):
    """Tema del evento, con dos documentos distintos o sin selección de documentos."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    evento_id: TextoNoVacio
    tema: TextoRecortado
    doc_base_id: TextoNoVacio | None = None
    doc_cambio_id: TextoNoVacio | None = None

    @model_validator(mode="after")
    def validar_documentos(self) -> "CompararVersionesParams":
        if (self.doc_base_id is None) != (self.doc_cambio_id is None):
            raise ValueError("Se requieren ambos ids de documento o ninguno")
        if self.doc_base_id is not None and self.doc_base_id == self.doc_cambio_id:
            raise ValueError("Los ids de documento deben ser distintos")
        return self
