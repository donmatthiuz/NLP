"""Validador puro de citas y datos literales: que el texto sea literal no garantiza fidelidad semántica."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, ValidationError

from .entrada import normalizar
from .esquemas import RespuestaEstructurada, TEXTO_ABSTENCION
from .generacion import Afirmacion, Dato, SalidaModelo, _neutralizar
from .herramientas import ResultadoHerramienta
from .lectura import FragmentoRecuperado, fuente_desde_fragmento
from .requisitos import ABREVIATURAS, MESES


class ErrorValidacion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codigo: str
    afirmacion: int | None = None
    cita: int | None = None


# Largo máximo de una cita tras colapsar los espacios. La seguridad depende de que la cita sea literal, no de su largo;
# el tope solo evita copiar el fragmento entero (y cabe en Fuente.cita, de 500).
MAX_CITA = 500

COMILLAS = str.maketrans({"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'"})


def _espacio_con_marca(c: str) -> bool:
    """Un carácter cuyo NFKC es un espacio y una marca combinante (´, ¨, ‾): sigue siendo un signo, no un espacio."""
    if c.isascii():
        return False
    p = unicodedata.normalize("NFKC", c)
    return len(p) > 1 and p[0].isspace() and unicodedata.category(p[1]).startswith("M")


def _nfkc(texto: str) -> str:
    """NFKC que deja intactos los caracteres de _espacio_con_marca, para que no se vuelvan un espacio."""
    trozos, inicio = [], 0
    for i, c in enumerate(texto):
        if _espacio_con_marca(c):
            trozos += [unicodedata.normalize("NFKC", texto[inicio:i]), c]
            inicio = i + 1
    trozos.append(unicodedata.normalize("NFKC", texto[inicio:]))
    return "".join(trozos)


def normalizar_cita(texto: str) -> str:
    return normalizar(_nfkc(texto).translate(COMILLAS))


MESES_INGLES = {"january", "february", "march", "april", "may", "june", "july", "august", "september",
                "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug",
                "sep", "sept", "oct", "nov", "dec"}
NOMBRES_MES = {*MESES, *ABREVIATURAS, *MESES_INGLES}
MARCADOR = re.compile(r"\{[1-9][0-9]*\}")
# El texto fuera de los marcadores: letras latinas con tilde española, espacios y puntuación simple.
# La "/" solo entre dos letras ("y/o"); se revisa aparte porque aquí no distingue el vecino.
TEXTO_PERMITIDO = re.compile(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ .,;:()¿?¡!\"'—–“”‘’«»/-]*")
BARRA_SUELTA = re.compile(r"(?<![^\W\d_])/|/(?![^\W\d_])")
SALTOS = re.compile(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
FALSO_FUENTE = re.compile(r"\[\s*\d+\s*\]")
VIGENCIA = re.compile(r"\b(?:vigent|vigenc|prevalec|sustitu|reemplaz|deroga|anula|sin efecto|valid|correct|queda sin)")
# Entre dos marcadores se omite la comprobación con estos tramos y con los que llevan una palabra de 4 o más letras;
# cualquier otro tramo corto debe estar en la cita con sus literales.
UNIONES = frozenset({", ", " y ", " o ", " ni ", " a ", " al ", ", y ", " y el "})
UNIDADES = ("día|días|mes|meses|año|años|hora|horas|minutos|semana|semanas|trimestre|trimestres|semestre|semestres|"
            "quincena|quincenas|por ciento|porcentaje|mg|ml|g|kg|unidades|viales|quetzales|dólares|millón|millones|"
            "mil|centavo|centavos|gramo|gramos|miligramo|miligramos|microgramo|microgramos|mcg|tableta|tabletas|"
            "frasco|frascos|ampolla|ampollas|litro|litros|cc")
UNIDAD_DESPUES = re.compile(r"\{[1-9][0-9]*\}\s+(?:" + normalizar(UNIDADES) + r")(?![^\W\d_])")
UNIDAD_ANTES = re.compile(r"(?<![\w$])(?:q\.?|gtq|us\$|\$)(?:\s+|\s*[(,]\s*)\{[1-9][0-9]*\}")
# Letras que parecen dígitos: una l minúscula junto a O, I, S, Z o B mayúscula, o letras sueltas de ese conjunto unidas por . , /
PARECE_DIGITO = re.compile(r"l[OISZB]|[OISZB]l")
PARECE_CIFRA_SUELTA = re.compile(r"(?<![^\W\d_])[lOISZB](?:[.,/][lOISZB])+(?![^\W\d_])")
# Palabra de solo I y O que parece una cifra: con dos O o con un signo interno ("IOO", "IO.OOO"); "SI", "ISO" y "III" no.
PARECE_CIFRA_IO = re.compile(r"(?<![^\W\d_])[IO]+(?:[.,][IO]+)*(?![^\W\d_])")
# Un tramo que no cabe en Dato.literal (200) no se convierte en dato: el texto falla con las reglas de siempre.
MAX_DATO = 200
# Palabra de 5 o más letras que no cuenta como contenido compartido entre una afirmación y su cita.
PALABRAS_VACIAS = frozenset({
    "entre", "sobre", "desde", "hasta", "segun", "cuando", "donde", "puede", "pueden", "deben", "estos", "estas",
    "otros", "otras", "tiene", "tienen", "sera", "seran", "cuales", "ambos", "mismo", "misma", "dicho", "dicha",
    "bases", "modificacion", "aclaracion", "documento", "documentos", "version", "evento", "licitacion"})
UNIDAD_SIGUE = re.compile(r"\s+(?:" + UNIDADES + r")(?![^\W\d_])", re.IGNORECASE)
PALABRA_LL = re.compile(r"(?<![^\W\d_])ll(?![^\W\d_])")
TIPOS_QUE_ESCALAN = {"modificacion", "aclaracion"}


def _espaciar(texto: str) -> str:
    return " ".join(_nfkc(texto).split())


def _signo(c: str) -> bool:
    """Ni letra, ni dígito, ni espacio."""
    return not (c.isalnum() or c.isspace())


def _continua(texto: str, posicion: int, paso: int, borde: str) -> bool:
    """El vecino alfanumérico, o cualquier signo pegado a un dígito, prolonga el tramo."""
    if not 0 <= posicion < len(texto):
        return False
    vecino = texto[posicion]
    if (borde.isalnum() and vecino.isalnum()) or (_signo(borde) and vecino.isdigit()):
        return True
    siguiente = posicion + paso
    return borde.isdigit() and _signo(vecino) and 0 <= siguiente < len(texto) and texto[siguiente].isdigit()


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
        pieza = c if _espacio_con_marca(c) else unicodedata.normalize("NFKC", c)
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


def _original(texto: str, tramo: str, plegar: bool, publicar: str | None = None) -> str | None:
    """El tramo del texto original que corresponde al tramo normalizado, con los espacios colapsados.

    Se busca en texto y se publica desde publicar (el mismo texto sin neutralizar, con los mismos índices)."""
    texto = unicodedata.normalize("NFC", texto)
    publicar = unicodedata.normalize("NFC", publicar) if publicar is not None else texto
    if len(publicar) != len(texto):
        publicar = texto
    plano, indices = _mapa(texto, plegar)
    if plano != (normalizar_cita(texto) if plegar else _espaciar(texto)):
        return None
    inicio = _buscar(plano, tramo)
    if inicio == -1:
        return None
    fin = indices[inicio + len(tramo) - 1] + 1
    while fin < len(texto) and unicodedata.category(texto[fin]).startswith("M"):
        fin += 1
    return " ".join(publicar[indices[inicio]:fin].split())


def _prohibido(texto: str) -> bool:
    """Caracteres de formato o letras que no son latinas; el texto ya va en NFKC."""
    return any(unicodedata.category(c) == "Cf" or (c.isalpha() and "LATIN" not in unicodedata.name(c, ""))
               for c in texto)


def _con_mes(texto: str) -> bool:
    return any(palabra in NOMBRES_MES for palabra in re.findall(r"[^\W\d_]+", normalizar(texto)))


def _aislado(texto: str) -> bool:
    """Cada marcador va solo: antes, inicio, espacio o (; después, espacio, final o una secuencia de .,;:) seguida de espacio o final."""
    marcadores = MARCADOR.findall(texto)
    if len(marcadores) != len(set(marcadores)):
        return False
    for m in MARCADOR.finditer(texto):
        antes = texto[m.start() - 1] if m.start() else " "
        cierre = len(texto[m.end():]) - len(texto[m.end():].lstrip(".,;:)"))
        fin = m.end() + cierre
        despues = texto[fin] if fin < len(texto) else " "
        if antes not in " (" or despues != " ":
            return False
    return True


def _compuestos(afirmacion, colocados=frozenset(), creados=frozenset()) -> list[list[str]]:
    """Los tramos de marcadores unidos por un texto que no es una unión simple, con el compuesto que deben formar en la cita.

    Entre un marcador que puso el código y un dato creado desde la cita la unión simple no exime: el compuesto debe estar en la cita."""
    compuestos, actual = [], None
    marcadores = list(MARCADOR.finditer(afirmacion.texto))
    for previo, m in zip(marcadores, marcadores[1:]):
        union = afirmacion.texto[previo.end():m.start()]
        union_nfkc = unicodedata.normalize("NFKC", union).lower()
        a, b = int(previo.group()[1:-1]), int(m.group()[1:-1])
        mixto = (a in colocados and b in creados) or (a in creados and b in colocados)
        # Un tramo con una palabra de 4 o más letras es contenido propio del modelo y no se exige en la cita.
        if (union_nfkc in UNIONES and not mixto) or any(len(p) >= 4 for p in re.findall(r"[^\W\d_]+", union_nfkc)):
            actual = None
        elif actual is None:
            actual = [previo.group(), union, m.group()]
            compuestos.append(actual)
        else:
            actual += [union, m.group()]
    return compuestos


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
    sin_marcadores = MARCADOR.sub(" ", afirmacion.texto)
    minusculas = nfkc.lower()
    if UNIDAD_DESPUES.search(normalizar(nfkc)) or UNIDAD_ANTES.search(minusculas):
        return "unidad_fuera_de_literal"
    # Las de categoría Nl (Ⅻ) son letras para NFKC: se revisan también antes de normalizar.
    if (any(unicodedata.category(c).startswith("N") for c in sin_marcadores + resto) or _con_mes(resto)
            or any(PARECE_DIGITO.search(p) for p in re.findall(r"[^\W\d_]+", resto))
            or PARECE_CIFRA_SUELTA.search(resto) or PALABRA_LL.search(resto)
            or any(p.count("O") >= 2 or not p.isalpha() for p in PARECE_CIFRA_IO.findall(resto))):
        return "dato_fuera_de_literal"
    if BARRA_SUELTA.search(resto) or not TEXTO_PERMITIDO.fullmatch(resto):
        return "texto_invalido"
    return None


def _palabras_de_contenido(texto: str) -> set[str]:
    """Palabras de 5 o más letras sin tilde ni mayúsculas, salvo las vacías y el nombre del documento."""
    return {p for p in re.findall(r"[^\W\d_]{5,}", normalizar_cita(texto)) if p not in PALABRAS_VACIAS}


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


def _poner_marcadores(afirmacion: Afirmacion) -> tuple[Afirmacion, int, frozenset[int]]:
    """Sustituye por {n} el literal copiado en el texto y descarta el dato que no aparece; devuelve los descartados
    y los números (tras renumerar) de los marcadores que puso.

    Solo actúa sobre datos sin marcador y con marcadores válidos; lo demás lo decide el validador sin cambios."""
    n = len(afirmacion.datos)
    usados = [int(m[1:-1]) for m in MARCADOR.findall(afirmacion.texto)]
    if len(usados) != len(set(usados)) or not set(usados) <= set(range(1, n + 1)):
        return afirmacion, 0, frozenset()
    # Se busca solo entre marcadores, para que un literal como "1" no caiga dentro de un "{1}".
    trozos = [[parte] for parte in MARCADOR.split(afirmacion.texto)]
    colocados = set()
    for i in sorted((i for i in range(1, n + 1) if i not in usados),
                    key=lambda i: -len(afirmacion.datos[i - 1].literal)):
        literal = afirmacion.datos[i - 1].literal
        for trozo in trozos:
            for t, texto in enumerate(trozo):
                posicion = -1 if isinstance(texto, int) else _buscar(texto, literal)
                if posicion != -1:
                    trozo[t:t + 1] = [texto[:posicion], i, texto[posicion + len(literal):]]
                    colocados.add(i)
                    break
            if i in colocados:
                break
    vigentes = [i for i in range(1, n + 1) if i in usados or i in colocados]
    if len(vigentes) == n and not colocados:
        return afirmacion, 0, frozenset()
    nuevo = {viejo: indice for indice, viejo in enumerate(vigentes, 1)}
    texto = ""
    for k, trozo in enumerate(trozos):
        if k:
            texto += "{%d}" % nuevo[usados[k - 1]]
        texto += "".join("{%d}" % nuevo[t] if isinstance(t, int) else t for t in trozo)
    ajustada = afirmacion.model_copy(update={"texto": texto, "datos": [afirmacion.datos[i - 1] for i in vigentes]})
    return ajustada, n - len(vigentes), frozenset(nuevo[i] for i in colocados)


def _es_dato(palabra: str) -> bool:
    """Una palabra con dígito, otro carácter numérico o nombre de mes."""
    nfkc = unicodedata.normalize("NFKC", palabra)
    return any(unicodedata.category(c).startswith("N") for c in palabra + nfkc) or _con_mes(nfkc)


def _tramos_de_datos(texto: str) -> list[tuple[int, int]]:
    """Posiciones de los tramos máximos de palabras con dígitos o mes, unidos solo por tramos cortos (sin palabras de 4 o más letras)."""
    tramos, actual = [], None
    for m in re.finditer(r"\S+", texto):
        palabra = m.group()
        sin_inicio = palabra.lstrip("(¿¡\"'«“‘")
        nucleo = sin_inicio.rstrip(".,;:)?!\"'»”’")
        if _es_dato(nucleo):
            inicio = m.start() + len(palabra) - len(sin_inicio)
            actual = [actual[0] if actual else inicio, inicio + len(nucleo)]
            if tramos and tramos[-1][0] == actual[0]:
                tramos.pop()
            tramos.append((actual[0], actual[1]))
        elif actual and any(len(p) >= 4 for p in re.findall(r"[^\W\d_]+", palabra)):
            actual = None
    return tramos


def _identificador(fragmento: FragmentoRecuperado | None) -> str | None:
    """El identificador de versión del fragmento (metadato de ingesta, no del modelo), con los espacios colapsados."""
    identificador = fragmento.identificador_version_oficial if fragmento else None
    return _espaciar(identificador) if identificador else None


def _en_identificador(fragmento: FragmentoRecuperado | None, literal: str) -> bool:
    """El literal es el identificador de versión del fragmento entero: una parte suelta ("1") no vale."""
    identificador = _identificador(fragmento)
    return identificador is not None and _espaciar(literal) == identificador


def _con_identificadores(texto: str, tramos: list[tuple[int, int]], identificadores: list[str]) -> list[tuple[int, int]]:
    """Cada tramo que toca un identificador completo del texto (con límites de palabra) se extiende a todo el identificador."""
    ocupados = []
    for identificador in identificadores:
        patron = r"(?<!\w)" + r"\s+".join(map(re.escape, identificador.split())) + r"(?!\w|[^\w\s]\d)"
        ocupados += [m.span() for m in re.finditer(patron, texto)]
    nuevos = []
    for inicio, fin in tramos:
        for a, b in ocupados:
            if inicio < b and a < fin:
                inicio, fin = min(inicio, a), max(fin, b)
        if not nuevos or inicio >= nuevos[-1][1]:
            nuevos.append((inicio, fin))
        else:
            nuevos[-1] = (nuevos[-1][0], max(fin, nuevos[-1][1]))
    return nuevos


def _datos_desde_cita(afirmacion: Afirmacion, evidencia: dict[str, FragmentoRecuperado]) -> tuple[Afirmacion, int]:
    """Sustituye por {n} el tramo con dígitos del texto que aparece tal cual en una cita de la afirmación
    o en el identificador de versión del fragmento citado; devuelve los creados.

    Lo que no aparece queda en el texto y lo rechaza _error_texto; las demás reglas corren después sobre el texto nuevo."""
    n = len(afirmacion.datos)
    usados = [int(m[1:-1]) for m in MARCADOR.findall(afirmacion.texto)]
    if len(usados) != len(set(usados)) or set(usados) != set(range(1, n + 1)):
        return afirmacion, 0
    citas = [_espaciar(c.cita) for c in afirmacion.citas]
    identificadores = [i for i in (_identificador(evidencia.get(c.fragmento)) for c in afirmacion.citas) if i]
    datos = list(afirmacion.datos)
    partes, marcadores = MARCADOR.split(afirmacion.texto), MARCADOR.findall(afirmacion.texto)
    texto = ""
    for k, parte in enumerate(partes):
        previo = 0
        for inicio, fin in _con_identificadores(parte, _tramos_de_datos(parte), identificadores):
            # La unidad que sigue al dato entra en el tramo si la cita la trae seguida.
            unidad = UNIDAD_SIGUE.match(parte, fin)
            if unidad and any(_buscar(c, _espaciar(parte[inicio:unidad.end()])) != -1 for c in citas):
                fin = unidad.end()
            literal = _espaciar(parte[inicio:fin])
            if SALTOS.search(parte[inicio:fin]) or any(c in literal for c in "[]{}") or len(literal) > MAX_DATO:
                continue
            donde = [j for j, cita in enumerate(citas, 1)
                     if _buscar(cita, literal) != -1
                     or _en_identificador(evidencia.get(afirmacion.citas[j - 1].fragmento), literal)]
            if not donde:
                continue
            propias = {d.cita for d in datos}
            datos.append(Dato(cita=next((j for j in donde if j in propias), donde[0]), literal=literal))
            texto += parte[previo:inicio] + "{%d}" % len(datos)
            previo = fin
        texto += parte[previo:] + (marcadores[k] if k < len(marcadores) else "")
    if len(datos) == n:
        return afirmacion, 0
    return afirmacion.model_copy(update={"texto": texto, "datos": datos}), len(datos) - n


def validar(salida_cruda: str, evidencia: dict[str, FragmentoRecuperado],
            resultado_herramienta: ResultadoHerramienta, *, evento_id: str,
            conflictos=(), informe: dict | None = None) -> RespuestaEstructurada | list[ErrorValidacion]:
    """Ocho etapas en orden; los errores solo llevan código y posiciones desde uno.

    En informe deja datos_descartados (los que el código quitó antes de validar) y datos_desde_cita (los que creó desde la cita)."""
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
        # En una abstención solo un posible_conflicto de la herramienta pide revisión humana.
        comunes["needs_human_review"] = bool(conflictos)
        return RespuestaEstructurada(answer=TEXTO_ABSTENCION, sources=[], abstained=True, **comunes)
    if not salida.afirmaciones:
        return [ErrorValidacion(codigo="sin_afirmaciones")]

    ajustadas = [_poner_marcadores(a) for a in salida.afirmaciones]
    salida = salida.model_copy(update={"afirmaciones": [a for a, _, _ in ajustadas]})
    if informe is not None:
        informe["datos_descartados"] = sum(d for _, d, _ in ajustadas)
    antes = [len(a.datos) for a in salida.afirmaciones]
    try:
        creadas = [_datos_desde_cita(a, evidencia) for a in salida.afirmaciones]
    except ValidationError:
        return [ErrorValidacion(codigo="esquema_invalido")]
    salida = salida.model_copy(update={"afirmaciones": [a for a, _ in creadas]})
    if informe is not None:
        informe["datos_desde_cita"] = sum(d for _, d in creadas)
    # Por afirmación: los marcadores que puso el código y los datos que creó desde la cita.
    colocados = [c for _, _, c in ajustadas]
    creados = [frozenset(range(n + 1, n + d + 1)) for n, (_, d) in zip(antes, creadas)]

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

    originales = {f.chunk_id: f.texto for f in resultado.fragmentos}
    for documento in resultado.documentos:
        for f in documento.fragmentos:
            originales.setdefault(f.chunk_id, f.texto)
    tramos, neutros = {}, {}
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        for j, cita in enumerate(afirmacion.citas, 1):
            literal = normalizar_cita(cita.cita)
            if len(literal) < 10 or sum(c.isalnum() for c in literal) < 10:
                errores.append(ErrorValidacion(codigo="cita_corta", afirmacion=i, cita=j))
            elif len(_espaciar(cita.cita)) > MAX_CITA:
                errores.append(ErrorValidacion(codigo="esquema_invalido", afirmacion=i, cita=j))
            else:
                f = evidencia[cita.fragmento]
                # Se busca en el texto neutralizado que vio el modelo y se publica el del documento, con los mismos índices.
                original = originales.get(f.chunk_id)
                if original is None or _neutralizar(original) != f.texto:
                    original = f.texto
                neutros[i, j] = _original(f.texto, literal, True)
                tramos[i, j] = _original(f.texto, literal, True, original)
                if tramos[i, j] is None:
                    errores.append(ErrorValidacion(codigo="cita_no_literal", afirmacion=i, cita=j))
    if errores:
        return errores

    literales = {}
    for i, afirmacion in enumerate(salida.afirmaciones, 1):
        if len({d.cita for d in afirmacion.datos}) > 1:
            errores.append(ErrorValidacion(codigo="datos_de_varias_citas", afirmacion=i))
            continue
        literales[i], neutrales = [], []
        for dato in afirmacion.datos:
            en_rango = dato.cita <= len(afirmacion.citas)
            publicado = (_original(neutros[i, dato.cita], _espaciar(dato.literal), False, tramos[i, dato.cita])
                         if en_rango and any(c.isalnum() for c in dato.literal) else None)
            neutral = (_original(neutros[i, dato.cita], _espaciar(dato.literal), False)
                       if publicado is not None else None)
            if publicado is None and en_rango and any(c.isalnum() for c in dato.literal) and _en_identificador(
                    evidencia[afirmacion.citas[dato.cita - 1].fragmento], dato.literal):
                publicado = neutral = _espaciar(dato.literal)
            if publicado is None:
                errores.append(ErrorValidacion(codigo="dato_no_literal", afirmacion=i,
                                               cita=dato.cita if en_rango else None))
                break
            literales[i].append(publicado)
            neutrales.append(neutral)
        if errores and errores[-1].afirmacion == i:
            continue
        # Entre dos marcadores, salvo una unión simple, el tramo con sus literales debe aparecer seguido en la cita.
        for compuesto in _compuestos(afirmacion, colocados[i - 1], creados[i - 1]):
            piezas = [neutrales[int(p[1:-1]) - 1] if MARCADOR.fullmatch(p) else p for p in compuesto]
            cita = afirmacion.datos[int(compuesto[0][1:-1]) - 1].cita
            if _buscar(normalizar_cita(neutros[i, cita]), normalizar_cita("".join(piezas))) == -1:
                errores.append(ErrorValidacion(codigo="dato_no_literal", afirmacion=i, cita=cita))
                break
    if errores:
        return errores

    lineas_armadas = [_armar(a, literales[i])[0] for i, a in enumerate(salida.afirmaciones, 1)]
    vistas = set()
    for i, linea in enumerate(lineas_armadas, 1):
        clave = normalizar_cita(linea)
        if clave in vistas:
            errores.append(ErrorValidacion(codigo="afirmacion_duplicada", afirmacion=i))
        vistas.add(clave)
    if errores:
        return errores
    # Con conflicto, la cita de un documento del grupo debe compartir una palabra de contenido con su afirmación:
    # así el modelo no rellena la segunda fuente repitiendo la afirmación con un fragmento ajeno.
    en_conflicto = {d for grupo in conflictos if len(set(grupo) & {f.doc_id for f in evidencia.values()}) >= 2
                    for d in grupo}
    for i, (afirmacion, linea) in enumerate(zip(salida.afirmaciones, lineas_armadas), 1):
        propias = _palabras_de_contenido(linea)
        for j, cita in enumerate(afirmacion.citas, 1):
            if (evidencia[cita.fragmento].doc_id in en_conflicto
                    and not propias & _palabras_de_contenido(neutros[i, j])):
                errores.append(ErrorValidacion(codigo="cita_ajena", afirmacion=i, cita=j))
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
        # Si estaba en la evidencia y se cita cualquier otro tipo de documento, la afirmación puede estar desactualizada.
        tipos_citados = {evidencia[c.fragmento].tipo_documento for a in salida.afirmaciones for c in a.citas}
        if tipos_citados & TIPOS_QUE_ESCALAN or (tipos_citados - TIPOS_QUE_ESCALAN and any(
                f.tipo_documento in TIPOS_QUE_ESCALAN for f in evidencia.values())):
            comunes["needs_human_review"] = True
        return RespuestaEstructurada(answer="\n".join(lineas), sources=fuentes, abstained=False, **comunes)
    except ValidationError:
        return [ErrorValidacion(codigo="fuente_invalida")]
