"""Validador puro de citas y datos literales: que el texto sea literal no garantiza fidelidad semántica."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, ValidationError

from .entrada import normalizar
from .esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from .generacion import SalidaModelo
from .herramientas import ResultadoHerramienta
from .lectura import FragmentoRecuperado, fuente_desde_fragmento
from .requisitos import ABREVIATURAS, MESES


class ErrorValidacion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codigo: str
    afirmacion: int | None = None
    cita: int | None = None


def normalizar_cita(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto)
    return normalizar(texto.translate(str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"',
                                                   "‘": "'", "’": "'"})))


MESES_INGLES = {"january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
                "sep", "sept", "oct", "nov", "dec"}
NOMBRES_MES = {*MESES, *ABREVIATURAS, *MESES_INGLES}
MARCADOR = re.compile(r"\{[1-9][0-9]*\}")
SALTOS = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
FALSO_FUENTE = re.compile(r"\[\s*\d+\s*\]")
VIGENCIA = re.compile(r"\b(?:vigent|vigenc|prevalec|sustitu|reemplaz|deroga|anula|sin efecto)")
TIPOS_QUE_ESCALAN = {"modificacion", "aclaracion"}


def _espaciar(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", texto).split())


def _continua(texto: str, posicion: int, paso: int, borde: str) -> bool:
    """El vecino alfanumérico, o un separador numérico entre dígitos, prolonga el tramo."""
    if not 0 <= posicion < len(texto):
        return False
    vecino = texto[posicion]
    if borde.isalnum() and vecino.isalnum():
        return True
    siguiente = posicion + paso
    return (borde.isdigit() and vecino in ".,/:-" and 0 <= siguiente < len(texto)
            and texto[siguiente].isdigit())


def _contiene(texto: str, tramo: str) -> bool:
    """El tramo está en el texto sin empezar ni terminar a mitad de una palabra o de un número."""
    inicio = texto.find(tramo) if tramo else -1
    while inicio != -1:
        fin = inicio + len(tramo)
        if not (_continua(texto, inicio - 1, -1, tramo[0]) or _continua(texto, fin, 1, tramo[-1])):
            return True
        inicio = texto.find(tramo, inicio + 1)
    return False


def _prohibido(texto: str) -> bool:
    """Caracteres de formato o letras que no son latinas; el texto ya va en NFKC."""
    return any(unicodedata.category(c) == "Cf" or (c.isalpha() and "LATIN" not in unicodedata.name(c, ""))
               for c in texto)


def _error_texto(afirmacion) -> str | None:
    """Los datos solo salen de los literales: en el texto no queda dígito ni mes fuera de un marcador."""
    # Fuera de alcance: cifras escritas con letras ("ciento veinte") y días en números romanos; los revisa una persona (I1, sección 3).
    nfkc = unicodedata.normalize("NFKC", afirmacion.texto)
    resto = unicodedata.normalize("NFKC", MARCADOR.sub(" ", afirmacion.texto))
    usados = {int(m[1:-1]) for m in MARCADOR.findall(afirmacion.texto)}
    if (SALTOS.search(afirmacion.texto) or _prohibido(nfkc) or FALSO_FUENTE.search(nfkc)
            or "{" in resto or "}" in resto or usados != set(range(1, len(afirmacion.datos) + 1))):
        return "texto_invalido"
    for dato in afirmacion.datos:
        literal = unicodedata.normalize("NFKC", dato.literal)
        if (SALTOS.search(dato.literal) or _prohibido(literal) or FALSO_FUENTE.search(literal)
                or "{" in literal or "}" in literal):
            return "texto_invalido"
    if (any(unicodedata.category(c).startswith("N") for c in resto)
            or any(palabra in NOMBRES_MES for palabra in re.findall(r"[^\W\d_]+", normalizar(resto)))):
        return "dato_fuera_de_literal"
    return None


def validar(salida_cruda: str, evidencia: dict[str, FragmentoRecuperado],
            resultado_herramienta: ResultadoHerramienta, *, evento_id: str,
            conflictos=()) -> RespuestaEstructurada | list[ErrorValidacion]:
    """Ocho etapas en orden; los errores solo llevan código y posiciones desde uno."""
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
        codigo = _error_texto(afirmacion)
        if codigo:
            errores.append(ErrorValidacion(codigo=codigo, afirmacion=i))
        if VIGENCIA.search(normalizar_cita(afirmacion.texto)):
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
            elif not _contiene(normalizar_cita(evidencia[cita.fragmento].texto), literal):
                errores.append(ErrorValidacion(codigo="cita_no_literal", afirmacion=i, cita=j))
    if errores:
        return errores

    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        if len({d.cita for d in afirmacion.datos}) > 1:
            errores.append(ErrorValidacion(codigo="datos_de_varias_citas", afirmacion=i))
            continue
        for dato in afirmacion.datos:
            en_rango = dato.cita <= len(afirmacion.citas)
            if not en_rango or not _contiene(_espaciar(afirmacion.citas[dato.cita - 1].cita),
                                             _espaciar(dato.literal)):
                errores.append(ErrorValidacion(codigo="dato_no_literal", afirmacion=i,
                                               cita=dato.cita if en_rango else None))
                break
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
            texto = MARCADOR.sub(lambda m: _espaciar(afirmacion.datos[int(m[0][1:-1]) - 1].literal),
                                 afirmacion.texto)
            lineas.append(texto + " " + "".join(marcadores))
        # Una modificación o aclaración como fuente basta para pedir revisión: el sistema no decide la vigencia.
        if any(evidencia[c.fragmento].tipo_documento in TIPOS_QUE_ESCALAN
               for a in salida.afirmaciones for c in a.citas):
            comunes["needs_human_review"] = True
        return RespuestaEstructurada(answer="\n".join(lineas), sources=fuentes, abstained=False, **comunes)
    except ValidationError:
        return [ErrorValidacion(codigo="fuente_invalida")]
