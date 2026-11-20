"""Lectura tolerante de lo que devuelve el rol 2: extra fuera, obligatorios siempre."""

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from .esquemas import Fuente

# Los tres tipos que emite _alertas() en src/licigt/recuperacion/busqueda.py.
TIPOS_ALERTA_CONOCIDOS = ("cobertura_incompleta", "posible_conflicto", "evento_con_modificaciones")


def es_tabla(texto: str) -> bool:
    """Fragmento de tabla de descripción: filas `| numeral | título | texto |`, a veces con la última cortada (el contrato del rol 2 no trae tipo_chunk)."""
    primera = next((l.strip() for l in texto.splitlines() if l.strip()), "")
    return primera.startswith("|") and primera.count("|") >= 3


class FragmentoRecuperado(BaseModel):
    """Fragmento de evidencia; los puntajes llegan según la variante y el origen."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    chunk_id: str
    doc_id: str
    tipo_documento: str
    version_ingesta: int
    pagina_inicio: int
    pagina_fin: int
    texto: str
    score: float
    seccion: str | None = None
    url_origen: str | None = None
    identificador_version_oficial: str | None = None
    pagina_impresa: int | None = None
    reranker: float | None = None
    semantico: float | None = None
    lexico: float | None = None
    rrf: float | None = None
    incluido_por: str | None = None

    @field_validator("pagina_impresa", mode="before")
    @classmethod
    def _impresa_tolerante(cls, valor):
        """Un número impreso dudoso (< 1, no entero) no rompe la cita: queda en None."""
        return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 1 else None


class Alerta(BaseModel):
    """Aviso del rol 2; el tipo es str para no romper la lectura ante uno nuevo."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    tipo: str
    doc_id: str
    documento: str | None = None
    status: str | None = None
    paginas_no_indexadas: list[int] | None = None
    numerales_modificados: list[str] = []
    # Numeral a letras de los literales que la modificación cambia, solo si todas sus menciones son de literales.
    literales_modificados: dict[str, list[str]] = {}
    chunk_ids_afectados: list[str] = []


class ResultadoBusqueda(BaseModel):
    """Lo que devuelve buscar(): evidencia, alertas y suficiencia."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    evento_id: str
    variante: str
    suficiente: StrictBool
    fragmentos: list[FragmentoRecuperado]
    alertas: list[Alerta] = []


class DocumentoComparado(BaseModel):
    """Un documento del evento con sus mejores fragmentos, según comparar_versiones()."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    doc_id: str
    tipo_documento: str
    identificador_version_oficial: str | None
    fragmentos: list[FragmentoRecuperado]


class ResultadoComparacion(BaseModel):
    """Lo que devuelve comparar_versiones(): documentos, sin alertas ni suficiencia."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    evento_id: str
    documentos: list[DocumentoComparado]


def fuente_desde_fragmento(fragmento: FragmentoRecuperado, cita: str) -> Fuente:
    """Convierte un fragmento recuperado en la cita estricta del contrato de salida."""
    return Fuente(
        doc_id=fragmento.doc_id,
        source=fragmento.url_origen or fragmento.doc_id,
        page=fragmento.pagina_inicio,
        page_end=fragmento.pagina_fin if fragmento.pagina_fin != fragmento.pagina_inicio else None,
        printed_page=fragmento.pagina_impresa,
        chunk_id=fragmento.chunk_id,
        version_ingesta=fragmento.version_ingesta,
        version_oficial=fragmento.identificador_version_oficial,
        cita=cita,
    )
