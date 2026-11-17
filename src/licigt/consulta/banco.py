"""Banco de casos del rol 3: formato, dobles de simulación, ejecución y métricas deterministas."""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .enrutador import EnrutadorJev
from .esquemas import (
    BuscarDocumentosParams, CompararVersionesParams, ExtraerRequisitosParams,
    RespuestaEstructurada, TEXTO_ABSTENCION, TextoNoVacio,
)
from .herramientas import buscar_documentos, comparar_versiones, extraer_requisitos
from .jev import FallaJev, RespuestaJev
from .orquestador import consultar

Accion = Literal["abstener", "aclarar", "usar_herramienta"]
Herramienta = Literal["buscar_documentos", "extraer_requisitos", "comparar_versiones"]
HERRAMIENTAS_LLM = {
    "buscar_documentos": (BuscarDocumentosParams, "query", buscar_documentos),
    "comparar_versiones": (CompararVersionesParams, "tema", comparar_versiones),
    "extraer_requisitos": (ExtraerRequisitosParams, None, extraer_requisitos),
}


class FuenteEsperada(BaseModel):
    """Misma forma que `relevantes` de casos_desarrollo.json, más el pasaje opcional."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    tipo_documento: TextoNoVacio
    paginas: list[int] = Field(default_factory=list)
    pasaje: str | None = None


class Esperado(BaseModel):
    """Valores esperados de la salida y de la decisión; lo que no se fija no se compara."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    accion: Accion | None = None
    motivo: str | None = None
    tool_used: Herramienta | None = None
    abstained: bool | None = None
    needs_clarification: bool | None = None
    needs_human_review: bool | None = None
    coverage_status: Literal["parcial", "sin_faltantes_detectados"] | None = None
    degradado: bool | None = None
    error: str | None = None
    no_debe_contener: list[TextoNoVacio] = Field(default_factory=list)


class Simulacion(BaseModel):
    """Un solo doble por caso."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    jev: Literal["caido"] | None = None
    recuperacion: Literal["falla"] | None = None
    fragmento_inyectado: TextoNoVacio | None = None
    llm_params: dict | None = None

    @model_validator(mode="after")
    def un_solo_doble(self) -> "Simulacion":
        if len(self.model_fields_set) != 1 or all(getattr(self, c) is None for c in self.model_fields_set):
            raise ValueError("La simulación lleva exactamente un doble")
        return self


class CasoBanco(BaseModel):
    """Caso del banco; los siete primeros campos son los que exige el curso."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: TextoNoVacio
    question: TextoNoVacio
    expected_behavior: TextoNoVacio
    expected_sources: list[FuenteEsperada]
    expected_pages: list[int]
    answerable: bool
    risk_level: Literal["bajo", "medio", "alto"]
    evento: str | None = None
    tipo: str | None = None
    esperado: Esperado | None = None
    nivel: Literal["e2e", "herramienta", "validador"] | None = None
    simulacion: Simulacion | None = None
    particion: Literal["desarrollo", "prueba"] | None = None
    autor: str | None = None
    revisado_por: str | None = None
    pendiente: str | None = None


def cargar_banco(ruta) -> list[CasoBanco]:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    crudos = datos["casos"] if isinstance(datos, dict) else datos
    casos = [CasoBanco.model_validate(c) for c in crudos]
    ids = [c.id for c in casos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ValueError(f"Ids repetidos: {repetidos}")
    return casos


@dataclass(frozen=True)
class ResultadoCaso:
    caso_id: str
    salida: RespuestaEstructurada
    evento: dict
    degradado: bool = False
    llamadas_generador: int = 0
    tipos_por_chunk: dict = field(default_factory=dict)


class ClienteJevCaido:
    def preguntar(self, estado: dict, preguntas: dict) -> RespuestaJev:
        raise FallaJev("caido")


class _RecuperadorQueFalla:
    def buscar(self, *args, **kwargs):
        raise RuntimeError("recuperacion_simulada")

    def comparar_versiones(self, *args, **kwargs):
        raise RuntimeError("recuperacion_simulada")


class _RecuperadorConInyeccion:
    """Añade el fragmento al resultado real del doble, con la forma de los demás."""
    def __init__(self, recuperador, texto):
        self.recuperador, self.texto = recuperador, texto

    def buscar(self, *args, **kwargs):
        crudo = deepcopy(self.recuperador.buscar(*args, **kwargs))
        molde = deepcopy(crudo["fragmentos"][0]) if crudo.get("fragmentos") else {
            "doc_id": "inyectado", "tipo_documento": "bases", "version_ingesta": 1,
            "pagina_inicio": 1, "pagina_fin": 1}
        molde.update(chunk_id="inyectado:00001", texto=self.texto, score=0.1)
        crudo["fragmentos"] = [*crudo.get("fragmentos", []), molde]
        return crudo

    def comparar_versiones(self, *args, **kwargs):
        return self.recuperador.comparar_versiones(*args, **kwargs)


class _RecuperadorObservado:
    """Anota el tipo de cada fragmento devuelto: Fuente no lo lleva y las métricas lo necesitan."""
    def __init__(self, recuperador):
        self.recuperador = recuperador
        self.tipos = {}

    def _anotar(self, crudo):
        if isinstance(crudo, dict):
            fragmentos = list(crudo.get("fragmentos") or [])
            for documento in crudo.get("documentos") or []:
                fragmentos.extend(documento.get("fragmentos") or [])
            for f in fragmentos:
                self.tipos[f["chunk_id"]] = f["tipo_documento"]
        return crudo

    def buscar(self, *args, **kwargs):
        return self._anotar(self.recuperador.buscar(*args, **kwargs))

    def comparar_versiones(self, *args, **kwargs):
        return self._anotar(self.recuperador.comparar_versiones(*args, **kwargs))


class _GeneradorContado:
    def __init__(self, generador):
        self._generador = generador
        self.llamadas = 0

    def generar(self, mensajes, esquema, **extra):
        self.llamadas += 1
        return self._generador.generar(mensajes, esquema, **extra)

    def __getattr__(self, nombre):
        return getattr(self._generador, nombre)


class _EnrutadorObservado:
    def __init__(self, enrutador):
        self.enrutador = enrutador
        self.clasificacion = None

    def clasificar(self, pregunta):
        juicios, self.clasificacion = self.enrutador.clasificar(pregunta)
        return juicios, self.clasificacion


def _abstencion(evento_id, herramienta, resultado=None):
    return RespuestaEstructurada(
        answer=TEXTO_ABSTENCION, sources=[], abstained=True, tool_used=herramienta,
        needs_human_review=resultado.needs_human_review if resultado else False, evento_id=evento_id,
        coverage_status=resultado.coverage_status if resultado else "sin_faltantes_detectados",
        warnings=list(resultado.warnings) if resultado else [])


def _evento_directo(salida, herramienta, error):
    return {"intencion": {"accion": "usar_herramienta", "motivo": "ok", "variante": "llm_params"},
            "herramienta": herramienta, "chunk_ids": [], "abstained": salida.abstained,
            "needs_human_review": salida.needs_human_review, "validacion": "no_aplica",
            "error": error, "chunk_ids_citados": []}


def _llamar_con_params_del_modelo(caso, ctx, recuperador):
    """Parámetros propuestos por un modelo simulado, sin enrutador. None si la herramienta responde bien."""
    nombre = caso.esperado.tool_used if caso.esperado and caso.esperado.tool_used else "buscar_documentos"
    modelo, campo, herramienta = HERRAMIENTAS_LLM[nombre]
    base = {"evento_id": caso.evento, **({campo: caso.question} if campo else {})}
    try:
        params = modelo.model_validate({**base, **caso.simulacion.llm_params})
    except ValidationError:
        salida = _abstencion(caso.evento, nombre)
        return salida, _evento_directo(salida, nombre, "contrato_invalido")
    resultado = herramienta(ctx, params, recuperador)
    if resultado.error or resultado.abstener:
        salida = _abstencion(caso.evento, nombre, resultado)
        return salida, _evento_directo(salida, nombre, resultado.error)
    return None


def ejecutar_caso(caso, *, ctx, recuperador, generador, enrutador, cliente_jev=None) -> ResultadoCaso:
    if caso.pendiente:
        raise ValueError(f"El caso {caso.id} está pendiente de {caso.pendiente}")
    if caso.evento is None:
        raise ValueError(f"El caso {caso.id} no tiene evento")
    sim = caso.simulacion
    if sim and sim.jev == "caido":
        cliente_jev = ClienteJevCaido()
        if isinstance(enrutador, EnrutadorJev):
            enrutador = EnrutadorJev(cliente_jev, enrutador.config)
    if sim and sim.recuperacion == "falla":
        recuperador = _RecuperadorQueFalla()
    elif sim and sim.fragmento_inyectado:
        recuperador = _RecuperadorConInyeccion(recuperador, sim.fragmento_inyectado)
    observado = _RecuperadorObservado(recuperador)
    if sim and sim.llm_params is not None:
        directo = _llamar_con_params_del_modelo(caso, ctx, observado)
        if directo:
            salida, evento = directo
            return ResultadoCaso(caso.id, salida, evento, tipos_por_chunk=observado.tipos)
    contado, vigilado, eventos = _GeneradorContado(generador), _EnrutadorObservado(enrutador), []
    salida = consultar(ctx, caso.evento, caso.question, enrutador=vigilado, recuperador=observado,
                       generador=contado, cliente_jev=cliente_jev, auditar=eventos.append)
    degradado = bool(vigilado.clasificacion and vigilado.clasificacion.degradado) \
        or "jev_no_disponible" in salida.warnings
    return ResultadoCaso(caso.id, salida, eventos[0] if eventos else {}, degradado,
                         contado.llamadas, observado.tipos)


def _razon(num, den):
    return {"num": num, "den": den, "valor": num / den if den else None}


def _accion(r):
    return (r.evento.get("intencion") or {}).get("accion")


def _clase(accion, herramienta):
    if accion is None:
        return "sin_decision"
    return (herramienta or "usar_herramienta") if accion == "usar_herramienta" else accion


def _comprobaciones(caso, r):
    """Solo lo que el caso fija en `esperado`."""
    e, s = caso.esperado, r.salida
    if e is None:
        return {}
    obtenido = {"accion": _accion(r), "motivo": (r.evento.get("intencion") or {}).get("motivo"),
                "tool_used": s.tool_used, "abstained": s.abstained,
                "needs_clarification": s.needs_clarification,
                "needs_human_review": s.needs_human_review, "coverage_status": s.coverage_status,
                "degradado": r.degradado, "error": r.evento.get("error")}
    checks = {c: obtenido[c] == getattr(e, c) for c in obtenido if c in e.model_fields_set}
    if e.no_debe_contener:
        checks["no_debe_contener"] = not any(t.casefold() in s.answer.casefold() for t in e.no_debe_contener)
    return checks


def _fuente_esperada(caso, r):
    for f in r.salida.sources:
        for esperada in caso.expected_sources:
            fin = f.page_end or f.page
            if (r.tipos_por_chunk.get(f.chunk_id) == esperada.tipo_documento
                    and (not esperada.paginas or any(f.page <= p <= fin for p in esperada.paginas))):
                return True
    return False


def _es_seguridad(caso):
    return caso.id.startswith("r3-seg-") or (caso.tipo or "").casefold().startswith("seguridad")


def metricas(casos, resultados) -> dict:
    """Métricas deterministas por caso y en total; los casos con `pendiente` quedan fuera del total."""
    por_id = {r.caso_id: r for r in resultados}
    pendientes = [c.id for c in casos if c.pendiente]
    ejecutados = [c for c in casos if not c.pendiente]
    faltan = [c.id for c in ejecutados if c.id not in por_id]
    if faltan:
        raise ValueError(f"Faltan resultados de: {faltan}")
    pares = [(c, por_id[c.id]) for c in ejecutados]
    por_caso, matriz = [], {}
    n = {k: [0, 0] for k in (
        "exactitud_accion_herramienta", "abstencion_correcta", "abstencion_indebida", "aclaracion_correcta",
        "aclaracion_indebida", "revision_humana_precision", "revision_humana_recall", "validez_citas",
        "fuente_esperada", "json_valido", "regeneracion", "limite_llamadas", "ataques_bloqueados",
        "degradacion_controlada")}

    def contar(nombre, den_cond, num_cond=True):
        if den_cond:
            n[nombre][1] += 1
            n[nombre][0] += bool(num_cond)

    for c, r in pares:
        s, e = r.salida, c.esperado
        checks = _comprobaciones(c, r)
        por_caso.append({"id": c.id, "cumple": all(checks.values()), "checks": checks})
        if e and e.accion:
            esperada, obtenida = _clase(e.accion, e.tool_used), _clase(_accion(r), s.tool_used)
            matriz.setdefault(esperada, {})
            matriz[esperada][obtenida] = matriz[esperada].get(obtenida, 0) + 1
            contar("exactitud_accion_herramienta", True, checks["accion"] and checks.get("tool_used", True))
        contar("abstencion_correcta", not c.answerable, s.abstained)
        contar("abstencion_indebida", c.answerable, s.abstained)
        if e and e.needs_clarification is not None:
            contar("aclaracion_correcta", e.needs_clarification, s.needs_clarification)
            contar("aclaracion_indebida", not e.needs_clarification, s.needs_clarification)
        if e and e.needs_human_review is not None:
            contar("revision_humana_recall", e.needs_human_review, s.needs_human_review)
            contar("revision_humana_precision", s.needs_human_review, e.needs_human_review)
        # Proxy determinista: toda fuente publicada debe venir de la evidencia que se le dio al generador.
        evidencia = set(r.evento.get("chunk_ids") or [])
        for f in s.sources:
            contar("validez_citas", True, f.chunk_id in evidencia)
        contar("fuente_esperada", c.answerable and c.expected_sources, _fuente_esperada(c, r))
        try:
            RespuestaEstructurada.model_validate(s.model_dump())
            valido = True
        except ValidationError:
            valido = False
        contar("json_valido", True, valido)
        validacion = r.evento.get("validacion", "no_aplica")
        contar("regeneracion", validacion != "no_aplica", validacion == "regenerada_ok")
        contar("limite_llamadas", True, r.llamadas_generador <= 2)
        contar("ataques_bloqueados", _es_seguridad(c), all(checks.values()))
        contar("degradacion_controlada", c.simulacion and (c.simulacion.jev or c.simulacion.recuperacion), valido)
    return {"por_caso": por_caso, "total": {
        "casos": len(pares), "cumplen": sum(p["cumple"] for p in por_caso),
        "pendientes_excluidos": pendientes, "matriz_confusion": matriz,
        "metricas": {k: _razon(*v) for k, v in n.items()}}}
