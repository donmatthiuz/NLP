"""Lista de verificación: modelos y propuesta determinista; este módulo no escribe nada."""

import re
import time
import unicodedata
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from .entrada import normalizar
from .esquemas import Categoria, Fuente, RespuestaEstructurada, TextoNoVacio
from .esquemas import ExtraerRequisitosParams
from .herramientas import ResultadoHerramienta, extraer_requisitos
from .lectura import fuente_desde_fragmento
from .orquestador import _RecuperadorObservado, _abstencion, _atributo_seguro, _registrar
from .preguntas_jev import ACTIVIDADES_CRONOGRAMA
from .validacion import _original, normalizar_cita

AVISO_LISTA = ("Los estados de la lista no certifican cumplimiento; la ausencia en los documentos cargados "
               "no prueba que no exista en el expediente.")
FECHA_SIN_VERIFICAR = "Fecha sin verificar"
ETIQUETAS_ACTIVIDAD = {
    "adquirir_documentos": "Adquisición de documentos",
    "induccion": "Inducción",
    "solicitud_aclaraciones": "Solicitud de aclaraciones",
    "respuesta_aclaraciones": "Respuesta de aclaraciones",
    "formulario_electronico": "Formulario electrónico",
    "recepcion_ofertas": "Recepción de ofertas",
    "apertura_plicas": "Apertura de plicas",
    "adjudicacion": "Adjudicación",
}
ETIQUETAS_FECHA = frozenset({*ETIQUETAS_ACTIVIDAD.values(), FECHA_SIN_VERIFICAR})
MOTIVO_REVISION_RESPUESTA = "Hay un posible conflicto entre documentos; requiere revisión humana"
MAX_TRAMO = 300
MIN_TRAMO_ORACION = 40
LARGO_MINIMO_CITA = 10
# Columnas intercaladas por la extracción del PDF: tres o más espacios entre dos textos.
SEPARACION_COLUMNAS = re.compile(r"(?<=\S) {3,}(?=\S)")
FIN_ORACION = re.compile(r"[.!?;:](?=\s|$)")
MOTIVO_FECHAS_DISTINTAS = "Las fuentes difieren; el sistema no decide cuál está vigente"

Caracter = Literal["fundamental", "no_fundamental", "no_indicado"]
Estado = Literal["pendiente", "preparado", "revisado"]


def caracter_de_seccion(seccion: str | None) -> Caracter:
    """Fundamental solo cuando la sección de la fuente lo dice; la primera frase contiene la segunda."""
    texto = normalizar(seccion or "")
    if "requisitos no fundamentales" in texto:
        return "no_fundamental"
    if "requisitos fundamentales" in texto:
        return "fundamental"
    return "no_indicado"


class ItemPropuesto(BaseModel):
    """Un ítem sin estado; su texto es una cita validada o una etiqueta del código, nunca texto libre."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    tipo: Literal["requisito", "fecha"]
    categoria: Categoria | None
    caracter: Caracter
    descripcion: TextoNoVacio
    fuentes: list[Fuente] = Field(min_length=1)
    requiere_revision: StrictBool
    motivo_revision: TextoNoVacio | None

    @model_validator(mode="after")
    def validar_texto(self) -> "ItemPropuesto":
        cita = self.fuentes[0].cita
        if self.tipo == "requisito":
            if self.descripcion != cita:
                raise ValueError("La descripción de un requisito es su cita")
        else:
            if self.caracter != "no_indicado" or self.categoria is not None:
                raise ValueError("Una fecha no lleva categoría ni carácter")
            if self.descripcion not in {f"{etiqueta}: {cita}" for etiqueta in ETIQUETAS_FECHA}:
                raise ValueError("La descripción de una fecha es una etiqueta conocida y su cita")
        if self.requiere_revision != (self.motivo_revision is not None):
            raise ValueError("El motivo de revisión va si y solo si se requiere revisión")
        return self


class PropuestaLista(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evento_id: TextoNoVacio
    respuesta: RespuestaEstructurada
    items: list[ItemPropuesto]

    @model_validator(mode="after")
    def validar_vacia(self) -> "PropuestaLista":
        if (self.respuesta.abstained or self.respuesta.needs_clarification) and self.items:
            raise ValueError("Con abstención o aclaración no hay ítems")
        return self


class ItemLista(ItemPropuesto):
    """Ítem guardado; el tenant_id vive en el repositorio, no en el ítem."""
    item_id: TextoNoVacio
    evento_id: TextoNoVacio
    estado: Estado
    creado_por: TextoNoVacio
    creado_en: AwareDatetime
    actualizado_por: TextoNoVacio
    actualizado_en: AwareDatetime


class CambioLista(BaseModel):
    """Historial al que solo se agregan filas."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: TextoNoVacio
    accion: Literal["alta", "estado"]
    estado_anterior: Estado | None
    estado_nuevo: Estado
    usuario: TextoNoVacio
    momento: AwareDatetime


def huella(evento_id: str, item: ItemPropuesto) -> tuple[str, str, str]:
    return evento_id, item.fuentes[0].chunk_id, item.descripcion


def _recortar(tramo: str) -> str:
    """Hasta MAX_TRAMO caracteres, en el último fin de oración (si deja un tramo razonable) o de palabra."""
    if len(tramo) <= MAX_TRAMO:
        return tramo
    ventana = tramo[:MAX_TRAMO + 1]
    fines = [m.end() for m in FIN_ORACION.finditer(ventana[:MAX_TRAMO]) if m.end() >= MIN_TRAMO_ORACION]
    if fines:
        return ventana[:fines[-1]]
    return ventana[:ventana.rfind(" ", 0, MAX_TRAMO + 1)] if " " in ventana else ventana[:MAX_TRAMO]


def tramo_literal(texto: str) -> str | None:
    """Primer tramo legible del fragmento con los espacios colapsados; es subcadena del texto, nada se genera."""
    bloque = re.split(r"\n\s*\n", texto.strip(), maxsplit=1)[0]
    if SEPARACION_COLUMNAS.search(texto):
        lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
        # Sin una línea libre de columnas, la primera columna de la primera línea.
        limpia = next((l for l in lineas if not SEPARACION_COLUMNAS.search(l)), None)
        bloque = limpia if limpia is not None else (SEPARACION_COLUMNAS.split(lineas[0])[0] if lineas else "")
    tramo = " ".join(bloque.split())
    return _recortar(tramo) if tramo else None


def _cita_valida(fragmento, cita: str) -> bool:
    """Las mismas comprobaciones con las que guardar revalida una cita contra su fragmento."""
    literal = normalizar_cita(cita)
    if len(literal) < LARGO_MINIMO_CITA or sum(c.isalnum() for c in literal) < LARGO_MINIMO_CITA:
        return False
    return _original(fragmento.texto, literal, True) == unicodedata.normalize("NFC", " ".join(cita.split()))


def proponer_items(resultado: ResultadoHerramienta, evento_id: str) -> list[ItemPropuesto]:
    """Función pura y sin LLM: un tramo literal por fragmento con categoría, más las fechas literales."""
    fragmentos = {f.chunk_id: f for f in resultado.fragmentos}
    items, vistos = [], set()

    def agregar(item: ItemPropuesto) -> None:
        if huella(evento_id, item) not in vistos:
            vistos.add(huella(evento_id, item))
            items.append(item)

    revisar = resultado.needs_human_review
    for fragmento in resultado.fragmentos:
        categoria = resultado.categorias.get(fragmento.chunk_id)
        if categoria is None:
            continue
        cita = tramo_literal(fragmento.texto)
        if cita is None or not _cita_valida(fragmento, cita):
            continue
        agregar(ItemPropuesto(
            tipo="requisito", categoria=categoria, caracter=caracter_de_seccion(fragmento.seccion),
            descripcion=cita, fuentes=[fuente_desde_fragmento(fragmento, cita)], requiere_revision=revisar,
            motivo_revision=MOTIVO_REVISION_RESPUESTA if revisar else None))

    distintas = {a.removeprefix("fechas_distintas: ") for a in resultado.warnings
                 if a.startswith("fechas_distintas: ")}
    for fecha in resultado.fechas:
        fragmento = fragmentos.get(fecha.chunk_id)
        if fecha.estado == "fuera_del_cronograma" or fragmento is None:
            continue
        etiqueta = ETIQUETAS_ACTIVIDAD.get(fecha.actividad or "", FECHA_SIN_VERIFICAR)
        motivo = FECHA_SIN_VERIFICAR if fecha.estado == "no_verificada" else None
        if fecha.actividad in distintas:
            motivo = MOTIVO_FECHAS_DISTINTAS
        agregar(ItemPropuesto(
            tipo="fecha", categoria=None, caracter="no_indicado",
            descripcion=f"{etiqueta}: {fecha.literal}",
            fuentes=[fuente_desde_fragmento(fragmento, fecha.literal)],
            requiere_revision=motivo is not None, motivo_revision=motivo))
    return items


def _respuesta_de_lista(evento_id: str, resultado: ResultadoHerramienta, items: list[ItemPropuesto]):
    fuentes = list({(i.fuentes[0].chunk_id, i.fuentes[0].cita): i.fuentes[0] for i in items}.values())
    return RespuestaEstructurada(
        answer=f"Propuesta de {len(items)} ítems tomados literalmente de los documentos del evento.",
        sources=fuentes, abstained=False, tool_used="extraer_requisitos",
        needs_human_review=resultado.needs_human_review, evento_id=evento_id,
        coverage_status=resultado.coverage_status, warnings=resultado.warnings)


def proponer_lista(ctx, evento_id, categoria=None, *, recuperador, cliente_jev=None,
                   auditar=lambda evento: None) -> PropuestaLista:
    """Acción del usuario, sin enrutador ni LLM: ejecuta extraer_requisitos con una pregunta fija y no escribe nada."""
    inicio = time.monotonic()
    usuario, tenant_id = _atributo_seguro(ctx, "usuario"), _atributo_seguro(ctx, "tenant_id")
    evento_salida = evento_id if isinstance(evento_id, str) and evento_id.strip() else "sin_evento"
    respuesta = _abstencion(evento_salida, herramienta="extraer_requisitos")
    resultado, items, error = None, [], None
    try:
        if evento_salida != evento_id:
            error = "parametros_invalidos"
        else:
            pregunta = f"Requisitos {categoria} y fechas del evento" if categoria else "Requisitos y fechas del evento"
            observado = _RecuperadorObservado(recuperador, evento_id)
            resultado = extraer_requisitos(
                ctx, ExtraerRequisitosParams(evento_id=evento_id, categoria=categoria, pregunta=pregunta),
                observado, cliente_jev=cliente_jev)
            error = resultado.error
            if observado.evento_distinto or resultado.evento_id != evento_id:
                error = "evento_distinto"
                respuesta = _abstencion(evento_salida, resultado, "citas_no_validas")
            elif resultado.abstener:
                respuesta = _abstencion(evento_salida, resultado)
            else:
                items = proponer_items(resultado, evento_id)
                respuesta = _respuesta_de_lista(evento_salida, resultado, items) if items else _abstencion(
                    evento_salida, resultado)
    except Exception:
        error, items = "falla_consulta", []
        respuesta = _abstencion(evento_salida, resultado, herramienta="extraer_requisitos")
    finally:
        _registrar(auditar, usuario, tenant_id, evento_salida, {"accion": "proponer_lista"}, respuesta,
                   resultado.fragmentos if resultado else [], "no_aplica", inicio, error, None)
    return PropuestaLista(evento_id=evento_salida, respuesta=respuesta, items=items)
