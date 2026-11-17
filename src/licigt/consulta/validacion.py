"""Validador puro de citas: el texto literal no garantiza fidelidad semántica."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, ValidationError

from .entrada import normalizar
from .esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from .generacion import SalidaModelo
from .herramientas import ResultadoHerramienta
from .lectura import FragmentoRecuperado, fuente_desde_fragmento
from .requisitos import fechas_en_texto, fechas_numericas_a_texto, normalizar_cifras


class ErrorValidacion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codigo: str
    afirmacion: int | None = None
    cita: int | None = None


def normalizar_cita(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto)
    return normalizar(texto.translate(str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"',
                                                   "‘": "'", "’": "'"})))


def _datos_sensibles(texto: str) -> set[str]:
    # Las cifras escritas con letras y los días en números romanos quedan fuera de esta comprobación determinista.
    texto = normalizar_cifras(fechas_numericas_a_texto(normalizar_cita(texto)))
    return {re.sub(r"^0+(?=[0-9])", "", n) for n in re.findall(r"[0-9]+(?:[.,/:\-][0-9]+)*", texto)}


def validar(salida_cruda: str, evidencia: dict[str, FragmentoRecuperado],
            resultado_herramienta: ResultadoHerramienta, *, evento_id: str,
            conflictos=()) -> RespuestaEstructurada | list[ErrorValidacion]:
    """Siete etapas en orden; los errores solo llevan código y posiciones desde uno."""
    try:
        salida = SalidaModelo.model_validate_json(salida_cruda, strict=True)
    except ValidationError as exc:
        errores = exc.errors(include_input=False, include_context=False, include_url=False)
        codigo = "json_invalido" if any(e["type"] == "json_invalid" for e in errores) else "esquema_invalido"
        return [ErrorValidacion(codigo=codigo)]

    resultado = resultado_herramienta
    comunes = dict(tool_used=resultado.herramienta, evento_id=evento_id,
                   needs_human_review=resultado.needs_human_review or salida.revision_humana,
                   coverage_status=resultado.coverage_status, warnings=resultado.warnings)
    if salida.abstener:
        return RespuestaEstructurada(answer=TEXTO_ABSTENCION, sources=[], abstained=True, **comunes)
    if not salida.afirmaciones:
        return [ErrorValidacion(codigo="sin_afirmaciones")]

    errores = []
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        if re.search(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]|\[[0-9]+\]", afirmacion.texto):
            errores.append(ErrorValidacion(codigo="texto_invalido", afirmacion=i))
        sin_formato = "".join(c for c in normalizar_cita(afirmacion.texto) if unicodedata.category(c) != "Cf")
        if re.search(r"\b(?:vigent|vigenc|prevalec|sustitu|reemplaz|deroga|anula|sin efecto)", sin_formato):
            comunes["needs_human_review"] = True
    if errores:
        return errores

    if resultado.evento_id != evento_id:
        errores.append(ErrorValidacion(codigo="evento_distinto"))
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        for j, cita in enumerate(afirmacion.citas, 1):
            if cita.fragmento not in evidencia:
                errores.append(ErrorValidacion(codigo="fragmento_desconocido", afirmacion=i, cita=j))
    if errores:
        return errores

    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        for j, cita in enumerate(afirmacion.citas, 1):
            literal = normalizar_cita(cita.cita)
            if len(literal) < 10 or sum(c.isalnum() for c in literal) < 10:
                errores.append(ErrorValidacion(codigo="cita_corta", afirmacion=i, cita=j))
            elif literal not in normalizar_cita(evidencia[cita.fragmento].texto):
                errores.append(ErrorValidacion(codigo="cita_no_literal", afirmacion=i, cita=j))
    if errores:
        return errores

    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        datos = set().union(*(_datos_sensibles(c.cita) for c in afirmacion.citas))
        fechas, meses = fechas_en_texto(afirmacion.texto)
        por_cita = [fechas_en_texto(c.cita) for c in afirmacion.citas]
        # Cada fecha completa sale de una sola cita; los meses sueltos, de la unión.
        if (not _datos_sensibles(afirmacion.texto) <= datos
                or not meses <= set().union(*(m for _, m in por_cita))
                or not all(any(fecha in f for f, _ in por_cita) for fecha in fechas)):
            errores.append(ErrorValidacion(codigo="dato_sin_respaldo", afirmacion=i))
    if errores:
        return errores

    citados = {evidencia[c.fragmento].doc_id for a in salida.afirmaciones for c in a.citas}
    disponibles = {f.doc_id for f in evidencia.values()}
    if resultado.herramienta == "comparar_versiones" and len(citados) < 2:
        return [ErrorValidacion(codigo="falta_segunda_fuente")]
    for grupo in conflictos:
        presentes = set(grupo) & disponibles
        if len(presentes) >= 2 and not presentes <= citados:
            return [ErrorValidacion(codigo="falta_segunda_fuente")]

    fuentes, indices, lineas = [], {}, []
    try:
        for afirmacion in salida.afirmaciones:
            marcadores = []
            for cita in afirmacion.citas:
                f = evidencia[cita.fragmento]
                fuente = fuente_desde_fragmento(f, cita.cita)
                pagina_fin = f.pagina_fin if f.pagina_fin != f.pagina_inicio else None
                if (fuente.chunk_id, fuente.doc_id, fuente.page, fuente.page_end,
                    fuente.version_ingesta, fuente.version_oficial) != (
                        f.chunk_id, f.doc_id, f.pagina_inicio, pagina_fin,
                        f.version_ingesta, f.identificador_version_oficial):
                    return [ErrorValidacion(codigo="fuente_invalida")]
                clave = (fuente.chunk_id, fuente.cita)
                if clave not in indices:
                    fuentes.append(fuente)
                    indices[clave] = len(fuentes)
                marcador = f"[{indices[clave]}]"
                if marcador not in marcadores:
                    marcadores.append(marcador)
            lineas.append(afirmacion.texto + " " + "".join(marcadores))
        return RespuestaEstructurada(answer="\n".join(lineas), sources=fuentes, abstained=False, **comunes)
    except ValidationError:
        return [ErrorValidacion(codigo="fuente_invalida")]
