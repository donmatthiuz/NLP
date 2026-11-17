"""Citation check de JEV después del validador: solo avisa y escala, nunca cambia el texto."""

import os
import re

from .esquemas import RespuestaEstructurada
from .jev import FallaJev, validar_respuesta

# Umbral del cookbook de citation check; no se ajusta hasta medir con casos_citas.json.
AUTO_ACCEPT = 0.8
OPCIONES = {
    "supports": "La sección afirma o implica que la afirmación es verdadera",
    "contradicts": "La sección afirma lo contrario o implica que la afirmación es falsa",
    "says_nothing": "La sección no trata lo que dice la afirmación",
}
MARCADORES = re.compile(r"\s*\[(\d+)\]")


def citas_activas() -> bool:
    return os.environ.get("LICIGT_CITAS_JEV") == "1"


def _afirmaciones(respuesta, fragmentos):
    """(afirmación sin marcadores, texto de las secciones citadas) por línea de la respuesta."""
    por_chunk = {f.chunk_id: f.texto for f in fragmentos}
    salida = []
    for linea in respuesta.answer.splitlines():
        indices = [int(n) for n in MARCADORES.findall(linea)]
        claim = MARCADORES.sub("", linea).strip()
        chunks = list(dict.fromkeys(respuesta.sources[n - 1].chunk_id for n in indices
                                    if 1 <= n <= len(respuesta.sources)))
        secciones = [por_chunk[c] for c in chunks if c in por_chunk]
        if claim and secciones:
            salida.append((claim, "\n\n".join(secciones)))
    return salida


def _con_aviso(respuesta, aviso, escalar):
    cambios = {"warnings": [*respuesta.warnings, aviso]}
    if escalar:
        cambios["needs_human_review"] = True
    return respuesta.model_copy(update=cambios)


def aplicar_citas(respuesta: RespuestaEstructurada, fragmentos, cliente):
    """Devuelve (respuesta, auditoría); la auditoría lleva modelo y códigos, sin texto."""
    if respuesta.abstained or respuesta.needs_clarification or not respuesta.sources:
        return respuesta, None
    afirmaciones = _afirmaciones(respuesta, fragmentos)
    if not afirmaciones:
        return respuesta, None
    # Solo salen la afirmación armada y el texto público de la sección citada.
    estado = {f"a{i}": {"claim": c, "section": s} for i, (c, s) in enumerate(afirmaciones, 1)}
    preguntas = {f"a{i}": {"type": "choice", "criteria": dict(OPCIONES),
                           "instructions": f"¿Cómo se relaciona `a{i}.section` con `a{i}.claim`?"}
                 for i in range(1, len(afirmaciones) + 1)}
    try:
        if cliente is None:
            raise FallaJev("cliente_no_disponible")
        jev = validar_respuesta(cliente.preguntar(estado, preguntas), preguntas)
    except FallaJev as exc:
        return _con_aviso(respuesta, "citas_jev_no_disponible", False), {"modelo": None, "codigos": [exc.codigo]}
    except Exception:
        return _con_aviso(respuesta, "citas_jev_no_disponible", False), {"modelo": None, "codigos": ["falla"]}
    codigos = []
    for i in range(1, len(afirmaciones) + 1):
        dato = jev.respuestas[f"a{i}"]
        if dato["choice"] != "supports":
            codigos.append(dato["choice"])
        elif dato["probabilities"]["supports"] < AUTO_ACCEPT:
            codigos.append("baja_confianza")
        else:
            codigos.append("supports")
    auditoria = {"modelo": jev.modelo, "codigos": codigos}
    sin_respaldo = sum(c != "supports" for c in codigos)
    if sin_respaldo:
        return _con_aviso(respuesta, f"cita_sin_respaldo_jev: {sin_respaldo}", True), auditoria
    return respuesta, auditoria
