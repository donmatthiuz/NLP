"""Señales auxiliares de entrada; no garantizan detectar toda inyección."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from .esquemas import NombreHerramienta, TextoRecortado

PATRONES_INYECCION = (
    r"\bignora\w*\b.{0,40}\b(?:instrucciones|reglas)\b", r"\bolvida\b.{0,20}\banterior\b",
    r"\b(?:revela|muestra|extrae)\b.{0,30}\bprompt\b", r"\bactua como\b", r"\beres ahora\b",
    r"\bignore\b.{0,40}\binstructions\b", r"\bsystem prompt\b",
    r"\bforget\b.{0,30}\b(?:previous|instructions)\b",
)
INICIO_PEDIDO = r"(?:^|[¿.!?]\s*|\b(?:puedes?|podrias?|quiero que|necesito que)\s+)"
PATRONES_PROHIBIDOS = (
    INICIO_PEDIDO + r"(?:presenta\w*|envia\w*|sube|subir)\b.{0,30}\b(?:ofertas?|tramites?)\b",
    r"\b(?:navega\w*|abre|abrir|visita\w*)\b.{0,30}\b(?:sitios?|enlaces?|https?)\b",
    INICIO_PEDIDO + r"(?:modifica|modificar|modifique|edita|editar|borra|borrar|elimina|eliminar)\b.{0,30}\b(?:documentos?|bases|anexos?)\b",
    r"\b(?:certifica|certificar|certifique)\b.{0,30}\bcumplimiento\b",
    r"\b(?:decide|decidir|recomienda\w*)\b.{0,50}\bparticipar\b",
    r"\b(?:debe|deberia|conviene)\b.{0,25}\bparticipar\b",
    r"\bdosis\b.{0,50}\b(?:pacientes?|ninos?|adultos?|administrar|tomar|dar)\b",
    r"\b(?:recomienda\w*|indica\w*|prescribe\w*)\b.{0,30}\b(?:dosis|tratamientos?|diagnosticos?|equivalencias? terapeuticas?)\b",
    r"\bdiagnostica\w*\b.{0,30}\bpacientes?\b",
    r"\b(?:dosis|tratamientos?|diagnosticos?|equivalencias? terapeuticas?)\b.{0,40}\b(?:recomienda\w*|pacientes?)\b",
)
PATRON_FECHA = r"\b(?:fechas?|plazos?|horas?)\b"
PATRON_ACTIVIDAD = (r"\b(?:recepcion|apertura|adjudicacion|presentacion|entrega|aclaraciones|consultas|"
                    r"publicacion|firma|pago|inicio|garantia|vigencia del contrato)\b")
ADAPTADOR_TEXTO = TypeAdapter(TextoRecortado)


class JuiciosEntrada(BaseModel):
    """Juicios y metadatos mínimos para decidir sin conservar la pregunta."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    longitud_valida: bool
    inyeccion: bool
    fuera_de_alcance: bool
    especifica: bool
    menciona_fecha: bool = False
    herramienta_reglas: NombreHerramienta | None = None


def normalizar(texto: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto.casefold())
                             if unicodedata.category(c) != "Mn").split())


def evaluar_entrada(pregunta: str) -> JuiciosEntrada:
    try:
        texto = normalizar(ADAPTADOR_TEXTO.validate_python(pregunta, strict=True))
    except ValidationError:
        return JuiciosEntrada(longitud_valida=False, inyeccion=False,
                              fuera_de_alcance=False, especifica=False)
    fecha = bool(re.search(PATRON_FECHA, texto))
    return JuiciosEntrada(
        longitud_valida=True,
        inyeccion=any(re.search(p, texto) for p in PATRONES_INYECCION),
        fuera_de_alcance=any(re.search(p, texto) for p in PATRONES_PROHIBIDOS),
        especifica=not fecha or bool(re.search(PATRON_ACTIVIDAD, texto)), menciona_fecha=fecha)
