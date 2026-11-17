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


COMILLAS = str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'"})


def normalizar_cita(texto: str) -> str:
    return normalizar(unicodedata.normalize("NFKC", texto).translate(COMILLAS))


MESES_INGLES = {"january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
                "sep", "sept", "oct", "nov", "dec"}
NOMBRES_MES = {*MESES, *ABREVIATURAS, *MESES_INGLES}
MARCADOR = re.compile(r"\{[1-9][0-9]*\}")
SEPARADORES = ".,/:-"
# El texto fuera de los marcadores: letras latinas con tilde española, espacios y puntuación simple.
TEXTO_PERMITIDO = re.compile(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ .,;:()¿?¡!\"'—–“”‘’«»-]*")
SALTOS = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
FALSO_FUENTE = re.compile(r"\[\s*\d+\s*\]")
VIGENCIA = re.compile(r"\b(?:vigent|vigenc|prevalec|sustitu|reemplaz|deroga|anula|sin efecto)")
TIPOS_QUE_ESCALAN = {"modificacion", "aclaracion"}


def _espaciar(texto: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", texto).split())


def _continua(texto: str, posicion: int, paso: int, borde: str) -> bool:
    """El vecino alfanumérico, o un separador numérico pegado a un dígito, prolonga el tramo."""
    if not 0 <= posicion < len(texto):
        return False
    vecino = texto[posicion]
    if (borde.isalnum() and vecino.isalnum()) or (borde in SEPARADORES and vecino.isdigit()):
        return True
    siguiente = posicion + paso
    return (borde.isdigit() and vecino in SEPARADORES and 0 <= siguiente < len(texto)
            and texto[siguiente].isdigit())


def _buscar(texto: str, tramo: str) -> int:
    """Posición del tramo en el texto sin empezar ni terminar a mitad de una palabra o de un número; -1 si no está."""
    inicio = texto.find(tramo) if tramo else -1
    while inicio != -1:
        fin = inicio + len(tramo)
        if not (_continua(texto, inicio - 1, -1, tramo[0]) or _continua(texto, fin, 1, tramo[-1])):
            return inicio
        inicio = texto.find(tramo, inicio + 1)
    return -1


def _mapa(texto: str, plegar: bool) -> tuple[str, list[int]]:
    """Normaliza como normalizar_cita (plegar) o como _espaciar, y da por carácter su posición en el original."""
    salida, indices = [], []
    for i, c in enumerate(texto):
        pieza = unicodedata.normalize("NFKC", c)
        if plegar:
            pieza = unicodedata.normalize("NFD", pieza.translate(COMILLAS).casefold())
        for ch in pieza:
            if plegar and unicodedata.category(ch) == "Mn":
                continue
            if not ch.isspace():
                salida.append(ch)
                indices.append(i)
            elif salida and salida[-1] != " ":
                salida.append(" ")
                indices.append(i)
    if salida and salida[-1] == " ":
        salida.pop()
        indices.pop()
    return "".join(salida), indices


def _original(texto: str, tramo: str, plegar: bool) -> str | None:
    """El tramo del texto original que corresponde al tramo normalizado, con los espacios colapsados."""
    plano, indices = _mapa(texto, plegar)
    if plano != (normalizar_cita(texto) if plegar else _espaciar(texto)):
        return None
    inicio = _buscar(plano, tramo)
    if inicio == -1:
        return None
    return " ".join(texto[indices[inicio]:indices[inicio + len(tramo) - 1] + 1].split())


def _prohibido(texto: str) -> bool:
    """Caracteres de formato o letras que no son latinas; el texto ya va en NFKC."""
    return any(unicodedata.category(c) == "Cf" or (c.isalpha() and "LATIN" not in unicodedata.name(c, ""))
               for c in texto)


def _con_mes(texto: str) -> bool:
    return any(palabra in NOMBRES_MES for palabra in re.findall(r"[^\W\d_]+", normalizar(texto)))


def _aislado(texto: str) -> bool:
    """Cada marcador va solo: antes, inicio, espacio o (; después, espacio, final o una secuencia de .,;) seguida de espacio o final."""
    marcadores = MARCADOR.findall(texto)
    if len(marcadores) != len(set(marcadores)):
        return False
    for m in MARCADOR.finditer(texto):
        antes = texto[m.start() - 1] if m.start() else " "
        cierre = len(texto[m.end():]) - len(texto[m.end():].lstrip(".,;)"))
        fin = m.end() + cierre
        despues = texto[fin] if fin < len(texto) else " "
        if antes not in " (" or despues != " ":
            return False
    return True


def _error_texto(afirmacion) -> str | None:
    """Los datos solo salen de los literales: en el texto no queda dígito ni mes fuera de un marcador."""
    # Fuera de alcance: cifras escritas con letras ("ciento veinte") y días en números romanos; los revisa una persona (I1, sección 3).
    # Riesgo residual: un mes partido con espacios o guiones ("oc tubre") requiere inyección y deja un texto visiblemente roto.
    nfkc = unicodedata.normalize("NFKC", afirmacion.texto)
    resto = unicodedata.normalize("NFKC", MARCADOR.sub(" ", afirmacion.texto))
    usados = {int(m[1:-1]) for m in MARCADOR.findall(afirmacion.texto)}
    if (SALTOS.search(afirmacion.texto) or FALSO_FUENTE.search(nfkc) or "{" in resto or "}" in resto
            or usados != set(range(1, len(afirmacion.datos) + 1))):
        return "texto_invalido"
    for dato in afirmacion.datos:
        literal = unicodedata.normalize("NFKC", dato.literal)
        if _prohibido(literal) or FALSO_FUENTE.search(literal) or "{" in literal or "}" in literal:
            return "texto_invalido"
    if not _aislado(afirmacion.texto):
        return "marcador_pegado"
    if any(unicodedata.category(c).startswith("N") for c in resto) or _con_mes(resto):
        return "dato_fuera_de_literal"
    if not TEXTO_PERMITIDO.fullmatch(resto):
        return "texto_invalido"
    return None


def _armar(afirmacion, literales: list[str]) -> tuple[str, str | None]:
    """Sustituye cada marcador por su literal y revisa la línea armada fuera de los tramos de literal."""
    partes = MARCADOR.split(afirmacion.texto)
    orden = [literales[int(m[1:-1]) - 1] for m in MARCADOR.findall(afirmacion.texto)]
    linea = partes[0] + "".join(literal + parte for literal, parte in zip(orden, partes[1:]))
    if FALSO_FUENTE.search(unicodedata.normalize("NFKC", linea)):
        return linea, "texto_invalido"
    if _con_mes(unicodedata.normalize("NFKC", " ".join(partes))):
        return linea, "dato_fuera_de_literal"
    return linea, None


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

    tramos = {}
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        for j, cita in enumerate(afirmacion.citas, 1):
            literal = normalizar_cita(cita.cita)
            if len(literal) < 10 or sum(c.isalnum() for c in literal) < 10:
                errores.append(ErrorValidacion(codigo="cita_corta", afirmacion=i, cita=j))
            elif len(_espaciar(cita.cita)) > 200:
                errores.append(ErrorValidacion(codigo="esquema_invalido", afirmacion=i, cita=j))
            else:
                tramos[i, j] = _original(evidencia[cita.fragmento].texto, literal, True)
                if tramos[i, j] is None:
                    errores.append(ErrorValidacion(codigo="cita_no_literal", afirmacion=i, cita=j))
    if errores:
        return errores

    literales = {}
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        if len({d.cita for d in afirmacion.datos}) > 1:
            errores.append(ErrorValidacion(codigo="datos_de_varias_citas", afirmacion=i))
            continue
        literales[i] = []
        for dato in afirmacion.datos:
            en_rango = dato.cita <= len(afirmacion.citas)
            publicado = _original(tramos[i, dato.cita], _espaciar(dato.literal), False) if en_rango else None
            if publicado is None:
                errores.append(ErrorValidacion(codigo="dato_no_literal", afirmacion=i,
                                               cita=dato.cita if en_rango else None))
                break
            literales[i].append(publicado)
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
        for i, afirmacion in enumerate(salida.afirmaciones, 1):
            marcadores = []
            for j, cita in enumerate(afirmacion.citas, 1):
                f = evidencia[cita.fragmento]
                fuente = fuente_desde_fragmento(f, tramos[i, j])
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
            linea, codigo = _armar(afirmacion, literales[i])
            if codigo:
                return [ErrorValidacion(codigo=codigo, afirmacion=i)]
            lineas.append(linea + " " + "".join(marcadores))
        # Una modificación o aclaración como fuente basta para pedir revisión: el sistema no decide la vigencia.
        if any(evidencia[c.fragmento].tipo_documento in TIPOS_QUE_ESCALAN
               for a in salida.afirmaciones for c in a.citas):
            comunes["needs_human_review"] = True
        return RespuestaEstructurada(answer="\n".join(lineas), sources=fuentes, abstained=False, **comunes)
    except ValidationError:
        return [ErrorValidacion(codigo="fuente_invalida")]
