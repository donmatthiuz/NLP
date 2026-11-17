"""Lista de verificación: modelos y propuesta determinista; este módulo no escribe nada."""

import time
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from .entrada import normalizar
from .esquemas import Categoria, Fuente, RespuestaEstructurada, TextoNoVacio
from .herramientas import ResultadoHerramienta
from .lectura import fuente_desde_fragmento
from .orquestador import _Ejecucion, _abstencion, _atributo_seguro, _ejecutar, _registrar
from .preguntas_jev import ACTIVIDADES_CRONOGRAMA
from .presupuesto import Presupuesto

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
MOTIVO_REVISION_RESPUESTA = "La respuesta requiere revisión humana"
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


def proponer_items(respuesta: RespuestaEstructurada, resultado: ResultadoHerramienta) -> list[ItemPropuesto]:
    """Función pura: los ítems salen de sources (ya validadas) y de las fechas literales, nunca de answer."""
    if respuesta.tool_used != "extraer_requisitos" or respuesta.abstained or respuesta.needs_clarification:
        return []
    fragmentos = {f.chunk_id: f for f in resultado.fragmentos}
    items, vistos = [], set()

    def agregar(item: ItemPropuesto) -> None:
        if huella(respuesta.evento_id, item) not in vistos:
            vistos.add(huella(respuesta.evento_id, item))
            items.append(item)

    for fuente in respuesta.sources:
        fragmento = fragmentos.get(fuente.chunk_id)
        revisar = respuesta.needs_human_review
        agregar(ItemPropuesto(
            tipo="requisito", categoria=resultado.categorias.get(fuente.chunk_id),
            caracter=caracter_de_seccion(fragmento.seccion if fragmento else None),
            descripcion=fuente.cita, fuentes=[fuente], requiere_revision=revisar,
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


def proponer_lista(ctx, evento_id, categoria=None, *, recuperador, generador, cliente_jev=None,
                   auditar=lambda evento: None) -> PropuestaLista:
    """Acción del usuario, sin enrutador: ejecuta extraer_requisitos con una pregunta fija y no escribe nada."""
    inicio = time.monotonic()
    usuario, tenant_id = _atributo_seguro(ctx, "usuario"), _atributo_seguro(ctx, "tenant_id")
    evento_salida = evento_id if isinstance(evento_id, str) and evento_id.strip() else "sin_evento"
    respuesta = _abstencion(evento_salida)
    ejecucion, items, error = _Ejecucion(), [], None
    try:
        if evento_salida != evento_id:
            error = "parametros_invalidos"
        else:
            pregunta = f"Requisitos {categoria} y fechas del evento" if categoria else "Requisitos y fechas del evento"
            respuesta = _ejecutar(ctx, evento_id, evento_salida, pregunta, "extraer_requisitos", Presupuesto(),
                                  recuperador=recuperador, generador=generador, cliente_jev=cliente_jev,
                                  ejecucion=ejecucion, categoria=categoria)
            error = ejecucion.error
            items = proponer_items(respuesta, ejecucion.resultado) if ejecucion.resultado else []
    except Exception:
        error, items = "falla_consulta", []
        respuesta = _abstencion(evento_salida, ejecucion.resultado, herramienta="extraer_requisitos")
    finally:
        _registrar(auditar, usuario, tenant_id, evento_salida, {"accion": "proponer_lista"}, respuesta,
                   ejecucion.fragmentos, ejecucion.validacion, inicio, error, generador)
    return PropuestaLista(evento_id=evento_salida, respuesta=respuesta, items=items)
