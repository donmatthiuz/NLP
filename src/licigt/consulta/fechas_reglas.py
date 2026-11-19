"""Verificación de las fechas del cronograma por reglas: la variante que adoptó el experimento F7b (Experimento_JEV.md).

Cada actividad tiene palabras clave tomadas de las definiciones de preguntas_jev.ACTIVIDADES_CRONOGRAMA. Una fecha queda
`verificada` con la actividad si su pasaje coincide con una sola; si no, `no_verificada`. Nunca asigna `ninguna`.
"""

import hashlib
import json
import re
import unicodedata

from .lectura import es_tabla
from .requisitos import FechaCandidata

# Sin tildes ni mayúsculas. Cambiar una palabra cambia la huella y deja de valer lo medido en el experimento.
PALABRAS_CLAVE = {
    "adquirir_documentos": (r"\badquirir\b",),
    "induccion": (r"\binduccion\b",),
    "solicitud_aclaraciones": (r"\bsolicitud de aclaraciones\b",),
    "respuesta_aclaraciones": (r"\brespuestas de aclaraciones\b",),
    "formulario_electronico": (r"\bformulario electronico\b",),
    "recepcion_ofertas": (r"\brecepcion de ofertas\b",),
    "apertura_plicas": (r"\bapertura de plicas\b",),
    "adjudicacion": (r"\badjudicar\b",),
}


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes)


def asignar_por_reglas(pasaje: str) -> str | None:
    """La actividad cuyas palabras clave aparecen en el pasaje; None si no hay una sola."""
    texto = _normalizar(pasaje)
    coincidencias = [actividad for actividad, patrones in PALABRAS_CLAVE.items()
                     if any(re.search(patron, texto) for patron in patrones)]
    return coincidencias[0] if len(coincidencias) == 1 else None


def texto_para_reglas(fila: dict, tabla: bool) -> str:
    """Fragmento de tabla: la fila que contiene la fecha (el pasaje compacta las filas y se corta donde empieza otra, `| |`).
    Fuera de tabla: el texto anterior y el literal, sin lo posterior (otra frase)."""
    pasaje, literal = fila["pasaje"], fila["fecha"]
    corte = pasaje.find(literal)
    if corte < 0:
        return pasaje
    fin = corte + len(literal)
    if tabla:
        otra_fila = re.search(r"\|\s*\|", pasaje[fin:])
        return pasaje if otra_fila is None else pasaje[:fin + otra_fila.start() + 1]
    return pasaje[:fin]


def huella_palabras_clave() -> str:
    """sha256 corto de las reglas (palabras clave y alcance): identifica qué reglas produjeron un veredicto."""
    reglas = {"palabras_clave": PALABRAS_CLAVE, "alcance": "solo_filas_de_tabla"}
    return hashlib.sha256(json.dumps(reglas, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def actividades_mencionadas(pasaje: str, literal: str, tabla: bool) -> list[str]:
    """Actividades cuyas palabras clave aparecen en el texto que miran las reglas, en orden alfabético."""
    texto = _normalizar(texto_para_reglas({"pasaje": pasaje, "fecha": literal}, tabla))
    return sorted(actividad for actividad, patrones in PALABRAS_CLAVE.items()
                  if any(re.search(patron, texto) for patron in patrones))


def estado_por_reglas(pasaje: str, literal: str, tabla: bool) -> dict:
    """Solo se verifica en filas de tabla, que es lo medido en F7b: fuera de una tabla la actividad no se asigna."""
    actividad = asignar_por_reglas(texto_para_reglas({"pasaje": pasaje, "fecha": literal}, tabla)) if tabla else None
    return ({"estado": "verificada", "actividad": actividad} if actividad
            else {"estado": "no_verificada", "actividad": None})


def verificar_fechas(fechas: list[FechaCandidata], candidatas: dict, tablas: dict):
    """Estado de cada fecha por reglas y, de las no verificadas que mencionan alguna actividad, cuáles menciona.

    `candidatas` es el resultado de armar_candidatas (c0, c1... en el orden de `fechas`); `tablas` dice, por chunk_id,
    si el fragmento es una tabla. Devuelve (fechas, {indice: actividades}). Una fecha sin ninguna actividad mencionada
    (una solvencia, por ejemplo) no es ambigua."""
    verificadas, ambiguas = [], {}
    for indice, (fecha, datos) in enumerate(zip(fechas, candidatas.values())):
        tabla = tablas.get(fecha.chunk_id, False)
        estado = estado_por_reglas(datos["pasaje"], datos["fecha"], tabla)
        if estado["estado"] == "no_verificada":
            mencionadas = actividades_mencionadas(datos["pasaje"], datos["fecha"], tabla)
            if mencionadas:
                ambiguas[indice] = mencionadas
        verificadas.append(FechaCandidata(**{**fecha.model_dump(), **estado}))
    return verificadas, ambiguas
