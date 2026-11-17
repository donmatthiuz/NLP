"""Lista de verificación: modelos y propuesta determinista; este módulo no escribe nada."""

import re
import time
from itertools import islice
import unicodedata
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from .entrada import normalizar
from .esquemas import Categoria, Fuente, RespuestaEstructurada, TextoNoVacio
from .esquemas import ExtraerRequisitosParams
from .herramientas import ResultadoHerramienta, extraer_requisitos
from .lectura import es_tabla, fuente_desde_fragmento
from .orquestador import _RecuperadorObservado, _abstencion, _atributo_seguro, _registrar
from .preguntas_jev import ACTIVIDADES_CRONOGRAMA
from .requisitos import MESES, encontrar_fechas
from .validacion import NUMERAL_FILA, TIPOS_QUE_ESCALAN, _original, normalizar_cita

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
# La banda de la respuesta ya dice que requiere revisión humana; el motivo del ítem solo explica por qué.
MOTIVO_REVISION_MODIFICACION = ("Una modificación o aclaración del evento toca esta sección; "
                                "el sistema no decide cuál está vigente")
MAX_TRAMO = 300
# La fila de una tabla (`título | texto`) cabe entera hasta el máximo de una cita.
MAX_TRAMO_FILA = 500
MIN_TRAMO_ORACION = 40
LARGO_MINIMO_CITA = 10
# Columnas intercaladas por la extracción del PDF: tres o más espacios entre dos textos.
SEPARACION_COLUMNAS = re.compile(r"(?<=\S) {3,}(?=\S)")
# Un ordinal ("7ª.", "1º.") o una abreviatura ("No.", "Art.") no cierran la oración.
FIN_ORACION = re.compile(r"(?<![ªº])(?<!\bNo)(?<!\bNúm)(?<!\bArts)(?<!\bArt)(?<!\bInc)(?<!\bLit)(?<!\bLic)(?<!\bSr)"
                         r"(?<!\bDr)(?<!\bAv)[.!?;:](?=\s|$)")
# Fila con numeral; queda el resto, `título | texto`.
FILA_CON_NUMERAL = re.compile(r"^\|\s*" + NUMERAL_FILA + r"\s*\|\s*(?P<resto>\S.*?)\s*\|?\s*$")
INICIO_FILA = re.compile(r"^\s*\|\s*" + NUMERAL_FILA + r"\s*\|\s*")
# Primer y segundo componente del numeral de una sección ("2.2" de "2.2.6 Recepción").
NUMERAL_PRINCIPAL = re.compile(r"^\s*(\d{1,2})(?:\.(\d{1,2}))?(?=[\s.]|$)")
PALABRA_DE_CONTENIDO = re.compile(r"[^\W\d_]{4,}")
MIN_PALABRAS_CONTENIDO = 4
MIN_RESTO_DE_FRASE = 40
MAX_PALABRAS_ENCABEZADO = 10
# Un tramo que termina en ":" con menos palabras de contenido que esto solo presenta una lista.
MIN_PALABRAS_PRESENTACION = 15
# Cuántos tramos legibles de un fragmento sin tabla se prueban hasta hallar uno que no sea basura.
MAX_TRAMOS_PROBADOS = 3
# El tramo de relevo (no el primero) debe cerrar una oración o llegar al corte por largo; si no, es el pedazo de una tabla.
FIN_DE_TRAMO = ".);:!?"
# Un numeral o literal al inicio ("a)", "d.7)", "1.", "2.27.4").
# Un entero suelto ("21 del REGLAMENTO).") es el resto de una referencia, no un numeral.
INICIO_NUMERAL = re.compile(r"^(?:\d+(?:\.\d+)+\.?|\d+[.)]|[A-Za-z](?:\.\d+)?\))(?=\s|$)")
PALABRA_CON_LETRAS = re.compile(r"[^\W\d_]{2,}")
# Un encabezado seguido solo de una referencia entre paréntesis: "ESPECIFICACIONES GENERALES. (Artículo 16 del REGLAMENTO)."
ENCABEZADO_CON_REFERENCIA = re.compile(r"^(?P<titulo>[^()]*?)\s*\([^()]*\)\s*\.?$")
# Un numeral que el texto de una modificación nombra ("numeral 2.7", "subnumeral 2.7.1"); como en el rol 2, solo X.Y o más.
NUMERAL_NOMBRADO = re.compile(r"(?:sub)?numeral\s+(\d+\.\d+(?:\.\d+)*)", re.IGNORECASE)
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


def _es_dato(palabra: str | None) -> bool:
    """Una palabra con dígito o nombre de mes: cortar a su lado deja fuera o parte un número o una fecha."""
    if not palabra:
        return False
    return any(c.isdigit() for c in palabra) or normalizar(palabra.strip(".,;:()")) in MESES


def _recortar(tramo: str, tope: int = MAX_TRAMO) -> str:
    """Hasta `tope` caracteres, en el último fin de oración (si deja un tramo razonable) o de palabra.

    Nunca justo antes de un número ni dentro de un dato (un número, una fecha)."""
    if len(tramo) <= tope:
        return tramo
    ventana = tramo[:tope + 1]
    fines = [m.end() for m in FIN_ORACION.finditer(ventana[:tope]) if m.end() >= MIN_TRAMO_ORACION
             and not _es_dato(next(iter(tramo[m.end():].split()), None))]
    if fines:
        return ventana[:fines[-1]]
    if " " not in ventana:
        return ventana[:tope]
    for corte in range(len(ventana) - 1, 0, -1):
        if ventana[corte] == " " and not _es_dato(next(iter(tramo[:corte].split()[-1:]), None)) \
                and not _es_dato(next(iter(tramo[corte:].split()), None)):
            return ventana[:corte]
    return ventana[:ventana.rfind(" ", 0, tope + 1)]


def _primer_bloque(texto: str) -> tuple[str, str]:
    """El primer bloque legible del texto (sin colapsar los espacios) y lo que queda después."""
    if SEPARACION_COLUMNAS.search(texto):
        lineas = [linea.strip() for linea in texto.splitlines()]
        # Desde la primera línea libre de columnas, las que siguen seguidas y libres también, hasta una línea en blanco
        # o con columnas: así la oración no se corta antes de un número que empieza la línea siguiente.
        inicio = next((i for i, l in enumerate(lineas) if l and not SEPARACION_COLUMNAS.search(l)), None)
        if inicio is None:
            primera = next((i for i, l in enumerate(lineas) if l), None)
            if primera is None:
                return "", ""
            return SEPARACION_COLUMNAS.split(lineas[primera])[0], "\n".join(lineas[primera + 1:])
        fin = next((i for i in range(inicio, len(lineas))
                    if not lineas[i] or SEPARACION_COLUMNAS.search(lineas[i])), len(lineas))
        return " ".join(lineas[inicio:fin]), "\n".join(lineas[fin:])
    partes = re.split(r"\n\s*\n", texto.strip(), maxsplit=1)
    return partes[0], partes[1] if len(partes) > 1 else ""


def tramos_literales(texto: str):
    """Los tramos legibles del fragmento en orden, con los espacios colapsados; cada uno es subcadena del texto."""
    while texto.strip():
        bloque, texto = _primer_bloque(texto)
        pendiente = " ".join(bloque.split())
        while pendiente:
            tramo = _recortar(pendiente)
            if not tramo:
                break
            yield tramo
            pendiente = pendiente[len(tramo):].strip()


def tramo_literal(texto: str) -> str | None:
    """Primer tramo legible del fragmento con los espacios colapsados; es subcadena del texto, nada se genera."""
    return next(tramos_literales(texto), None)


def tramos_de_tabla(texto: str) -> list[str]:
    """Un tramo por fila con numeral: el `título | texto` contiguo de la fila, entero hasta 500 caracteres; el encabezado se salta."""
    tramos = []
    for linea in texto.splitlines():
        fila = FILA_CON_NUMERAL.match(linea.strip())
        if fila:
            tramos.append(_recortar(" ".join(fila["resto"].split()), MAX_TRAMO_FILA))
    return tramos


def _es_basura(cita: str) -> bool:
    """Una presentación de lista, un encabezado, un resto de frase o un tramo de menos de 4 palabras de contenido no es un requisito."""
    palabras = len(PALABRA_DE_CONTENIDO.findall(cita))
    if cita.rstrip().endswith(":") and palabras < MIN_PALABRAS_PRESENTACION:
        return True
    referencia = ENCABEZADO_CON_REFERENCIA.match(cita)
    if referencia:
        titulo = [c for c in referencia["titulo"] if c.isalpha()]
        if titulo and not any(c.islower() for c in titulo):
            return True
    numeral = INICIO_NUMERAL.match(cita)
    if numeral and any(p.islower() for p in PALABRA_CON_LETRAS.findall(cita[numeral.end():])):
        return False
    if palabras < MIN_PALABRAS_CONTENIDO:
        return True
    letras = [c for c in cita if c.isalpha()]
    if letras and not any(c.islower() for c in letras) and len(cita.split()) <= MAX_PALABRAS_ENCABEZADO:
        return True
    return cita[:1].islower() and len(cita) < MIN_RESTO_DE_FRASE


def _numeral_principal(seccion: str | None) -> str | None:
    """"2.2" de "2.2.6 Recepción" y de "2.2   CRONOGRAMA"; None si la sección no empieza por un numeral."""
    m = NUMERAL_PRINCIPAL.match(seccion or "")
    return ".".join(g for g in m.groups() if g) if m else None


def _numeral_doble(texto: str | None) -> str | None:
    """El numeral principal solo si tiene al menos dos componentes ("2.2"); "2 vial, Código IGSS…" no es un numeral."""
    principal = _numeral_principal(texto)
    return principal if principal and "." in principal else None


def _numerales_tocados(resultado: ResultadoHerramienta) -> set[str]:
    """Numerales principales que una modificación o aclaración puede cambiar: los de la alerta, el de su sección y los que su texto nombra."""
    tocados = {_numeral_doble(n) for conflicto in resultado.conflictos for n in conflicto.numerales}
    for f in resultado.fragmentos:
        if f.tipo_documento in TIPOS_QUE_ESCALAN:
            tocados.add(_numeral_doble(f.seccion))
            tocados.update(_numeral_doble(n) for n in NUMERAL_NOMBRADO.findall(f.texto))
    return tocados - {None}


def _cita_de_fecha(fragmento, literal: str, ocurrencia: int) -> str:
    """En una tabla, el tramo contiguo de la fila desde el título hasta la fecha; si no, la fecha sola."""
    texto = fragmento.texto
    if not es_tabla(texto):
        return literal
    posiciones = [p for l, _, p in encontrar_fechas(texto) if l == literal]
    if ocurrencia >= len(posiciones):
        return literal
    fin = posiciones[ocurrencia] + len(literal)
    fila = texto[texto.rfind("\n", 0, posiciones[ocurrencia]) + 1:fin]
    inicio = INICIO_FILA.match(fila)
    cita = " ".join((fila[inicio.end():] if inicio else fila.lstrip(" |")).split())
    if len(cita) > MAX_TRAMO_FILA:
        cita = cita[len(cita) - MAX_TRAMO_FILA:].split(" ", 1)[-1]
    return cita if _cita_valida(fragmento, cita) else literal


def _cita_valida(fragmento, cita: str) -> bool:
    """Las mismas comprobaciones con las que guardar revalida una cita contra su fragmento."""
    literal = normalizar_cita(cita)
    if len(literal) < LARGO_MINIMO_CITA or sum(c.isalnum() for c in literal) < LARGO_MINIMO_CITA:
        return False
    return _original(fragmento.texto, literal, True) == unicodedata.normalize("NFC", " ".join(cita.split()))


def proponer_items(resultado: ResultadoHerramienta, evento_id: str) -> list[ItemPropuesto]:
    """Función pura y sin LLM: un tramo literal por fragmento con categoría (uno por fila en las tablas), más las fechas literales."""
    fragmentos = {f.chunk_id: f for f in resultado.fragmentos}
    items, vistos = [], set()

    def agregar(item: ItemPropuesto) -> None:
        if huella(evento_id, item) not in vistos:
            vistos.add(huella(evento_id, item))
            items.append(item)

    # Solo piden revisión los ítems que una modificación o aclaración puede afectar: un fragmento afectado, uno del
    # documento que cambia, o uno de una sección cuyo numeral principal se modifica.
    afectados = {c for conflicto in resultado.conflictos for c in conflicto.chunk_ids_afectados}
    documentos = {conflicto.doc_id for conflicto in resultado.conflictos}
    tocados = _numerales_tocados(resultado)

    def toca(fragmento) -> bool:
        return (fragmento.chunk_id in afectados or fragmento.doc_id in documentos
                or _numeral_principal(fragmento.seccion) in tocados)

    for fragmento in resultado.fragmentos:
        categoria = resultado.categorias.get(fragmento.chunk_id)
        if categoria is None:
            continue
        motivo = MOTIVO_REVISION_MODIFICACION if toca(fragmento) else None

        def aceptable(cita) -> bool:
            return cita is not None and not _es_basura(cita) and _cita_valida(fragmento, cita)

        if es_tabla(fragmento.texto):
            citas = tramos_de_tabla(fragmento.texto)
        else:
            # Un solo tramo: el primero legible que no sea basura (el fragmento no se pierde por empezar con un encabezado).
            primero = next((t for n, t in enumerate(islice(tramos_literales(fragmento.texto), MAX_TRAMOS_PROBADOS))
                            if aceptable(t) and (n == 0 or t[-1] in FIN_DE_TRAMO or len(t) >= MAX_TRAMO - 40)), None)
            citas = [primero]
        for cita in citas:
            if not aceptable(cita):
                continue
            agregar(ItemPropuesto(
                tipo="requisito", categoria=categoria, caracter=caracter_de_seccion(fragmento.seccion),
                descripcion=cita, fuentes=[fuente_desde_fragmento(fragmento, cita)],
                requiere_revision=motivo is not None, motivo_revision=motivo))

    distintas = {a.removeprefix("fechas_distintas: ") for a in resultado.warnings
                 if a.startswith("fechas_distintas: ")}
    ocurrencias = {}
    for fecha in resultado.fechas:
        fragmento = fragmentos.get(fecha.chunk_id)
        # La n-ésima fecha con el mismo literal de un fragmento es la n-ésima de encontrar_fechas.
        ocurrencia = ocurrencias[fecha.chunk_id, fecha.literal] = ocurrencias.get((fecha.chunk_id, fecha.literal), -1) + 1
        if fecha.estado == "fuera_del_cronograma" or fragmento is None:
            continue
        cita = _cita_de_fecha(fragmento, fecha.literal, ocurrencia)
        etiqueta = ETIQUETAS_ACTIVIDAD.get(fecha.actividad or "", FECHA_SIN_VERIFICAR)
        motivo = FECHA_SIN_VERIFICAR if fecha.estado == "no_verificada" else None
        if fecha.actividad in distintas:
            motivo = MOTIVO_FECHAS_DISTINTAS
        if motivo is None and toca(fragmento):
            motivo = MOTIVO_REVISION_MODIFICACION
        agregar(ItemPropuesto(
            tipo="fecha", categoria=None, caracter="no_indicado",
            descripcion=f"{etiqueta}: {cita}",
            fuentes=[fuente_desde_fragmento(fragmento, cita)],
            requiere_revision=motivo is not None, motivo_revision=motivo))
    return items


def _respuesta_de_lista(evento_id: str, resultado: ResultadoHerramienta, items: list[ItemPropuesto]):
    fuentes = list({(i.fuentes[0].chunk_id, i.fuentes[0].cita): i.fuentes[0] for i in items}.values())
    return RespuestaEstructurada(
        answer=f"Propuesta de {len(items)} ítems tomados literalmente de los documentos del evento.",
        sources=fuentes, abstained=False, tool_used="extraer_requisitos",
        # Como validacion.py: una modificación o aclaración en la evidencia basta para pedir revisión.
        needs_human_review=resultado.needs_human_review or any(
            f.tipo_documento in TIPOS_QUE_ESCALAN for f in resultado.fragmentos), evento_id=evento_id,
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
