"""Herramientas de solo lectura: evidencia del rol 2 traducida para la generación."""

import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from .esquemas import (
    BuscarDocumentosParams, Categoria, CompararVersionesParams, ExtraerRequisitosParams, NombreHerramienta,
)
from .jev import ClienteJev, FallaJev, validar_respuesta
from .lectura import (
    TIPOS_ALERTA_CONOCIDOS, Alerta, DocumentoComparado, FragmentoRecuperado,
    ResultadoBusqueda, ResultadoComparacion,
)
from .preguntas_jev import CHOICE_MIN, MAX_CANDIDATAS_JEV, NOUL_SI, preguntas_fechas
from .requisitos import (
    CONSULTAS_POR_CATEGORIA, CONSULTA_CRONOGRAMA, FechaCandidata, encontrar_fechas,
)


class Recuperador(Protocol):
    """Firmas exactas del rol 2; licigt.recuperacion.busqueda las cumple por tipado estructural."""

    def buscar(self, ctx, evento_id: str, pregunta: str, variante: str = "mejorada",
               k: int = 5, conn=None) -> dict: ...

    def comparar_versiones(self, ctx, evento_id: str, pregunta: str, k: int = 2,
                           conn=None) -> dict: ...


class ResultadoHerramienta(BaseModel):
    """Resultado intermedio que consume la generación (F4); nunca lleva texto de respuesta."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    herramienta: NombreHerramienta
    evento_id: str
    fragmentos: list[FragmentoRecuperado]
    documentos: list[DocumentoComparado] = []
    fechas: list[FechaCandidata] = []
    # Del chunk_id a la categoría de la primera consulta fija que lo recuperó; el cronograma no asigna.
    categorias: dict[str, Categoria] = {}
    abstener: StrictBool
    needs_human_review: StrictBool
    coverage_status: Literal["parcial", "sin_faltantes_detectados"]
    warnings: list[str]
    error: Literal["falla_recuperacion", "contrato_invalido", "documento_fuera_del_evento"] | None


def _fallo(herramienta: NombreHerramienta, evento_id: str,
           error: Literal["falla_recuperacion", "contrato_invalido",
                          "documento_fuera_del_evento"]) -> ResultadoHerramienta:
    """Falla controlada: se abstiene sin evidencia y sin lanzar nada hacia afuera."""
    return ResultadoHerramienta(
        herramienta=herramienta, evento_id=evento_id, fragmentos=[], abstener=True,
        needs_human_review=False, coverage_status="sin_faltantes_detectados",
        warnings=[], error=error)


def _aviso_cobertura(alerta: Alerta) -> str:
    """doc_id y páginas sin indexar; el status solo cuando no hay páginas."""
    if alerta.paginas_no_indexadas:
        detalle = "páginas no indexadas " + ", ".join(map(str, alerta.paginas_no_indexadas))
    elif alerta.status:
        detalle = "status " + alerta.status
    else:
        detalle = "sin páginas reportadas"
    return f"cobertura_incompleta: {alerta.doc_id} {detalle}"


def _interpretar(alertas: list[Alerta]):
    """Traduce las alertas del rol 2 a revisión humana, cobertura y advertencias cortas."""
    revisar, parcial, avisos = False, False, []
    for alerta in alertas:
        if alerta.tipo not in TIPOS_ALERTA_CONOCIDOS:
            avisos.append(f"alerta_desconocida: {alerta.tipo}")
        elif alerta.tipo == "posible_conflicto":
            revisar = True
        elif alerta.tipo == "cobertura_incompleta":
            parcial = True
            avisos.append(_aviso_cobertura(alerta))
        else:  # evento_con_modificaciones
            avisos.append(f"evento_con_modificaciones: {alerta.doc_id}")
    return revisar, parcial, avisos


def buscar_documentos(ctx, params: BuscarDocumentosParams,
                      recuperador: Recuperador) -> ResultadoHerramienta:
    """Evidencia del evento filtrada por tipo, conservando ambas fuentes de un conflicto."""
    try:
        crudo = recuperador.buscar(ctx, params.evento_id, params.query,
                                   variante="mejorada", k=params.k)
    except Exception:
        return _fallo("buscar_documentos", params.evento_id, "falla_recuperacion")
    try:
        resultado = ResultadoBusqueda.model_validate(crudo)
    except ValidationError:
        return _fallo("buscar_documentos", params.evento_id, "contrato_invalido")

    revisar, parcial, avisos = _interpretar(resultado.alertas)
    fragmentos = resultado.fragmentos
    if params.tipo_documento is not None:
        # doc_id conserva el cambio, incluido_por los añadidos y chunk_ids_afectados las bases.
        en_conflicto = {a.doc_id for a in resultado.alertas if a.tipo == "posible_conflicto"}
        afectados = {chunk_id for a in resultado.alertas if a.tipo == "posible_conflicto"
                     for chunk_id in a.chunk_ids_afectados}
        fragmentos = [f for f in fragmentos if f.tipo_documento == params.tipo_documento
                      or f.incluido_por == "posible_conflicto" or f.doc_id in en_conflicto
                      or f.chunk_id in afectados]
        if not fragmentos:
            avisos.append(f"sin_fragmentos_del_tipo: {params.tipo_documento}")
    return ResultadoHerramienta(
        herramienta="buscar_documentos", evento_id=params.evento_id, fragmentos=fragmentos,
        abstener=not resultado.suficiente or not fragmentos, needs_human_review=revisar,
        coverage_status="parcial" if parcial else "sin_faltantes_detectados",
        warnings=avisos, error=None)


def comparar_versiones(ctx, params: CompararVersionesParams,
                       recuperador: Recuperador) -> ResultadoHerramienta:
    """Contrasta los documentos del evento; la vigencia la decide una persona, nunca el sistema."""
    try:
        comparacion_cruda = recuperador.comparar_versiones(ctx, params.evento_id, params.tema, k=2)
        busqueda_cruda = recuperador.buscar(ctx, params.evento_id, params.tema,
                                            variante="mejorada", k=5)
    except Exception:
        return _fallo("comparar_versiones", params.evento_id, "falla_recuperacion")
    try:
        comparacion = ResultadoComparacion.model_validate(comparacion_cruda)
        busqueda = ResultadoBusqueda.model_validate(busqueda_cruda)
    except ValidationError:
        return _fallo("comparar_versiones", params.evento_id, "contrato_invalido")

    revisar, parcial, avisos = _interpretar(busqueda.alertas)
    documentos = comparacion.documentos
    if params.doc_base_id is not None:
        pedidos = {params.doc_base_id, params.doc_cambio_id}
        if not pedidos <= {d.doc_id for d in documentos}:
            return _fallo("comparar_versiones", params.evento_id, "documento_fuera_del_evento")
        documentos = [d for d in documentos if d.doc_id in pedidos]
    documentos = [d for d in documentos if d.fragmentos]
    revisar = revisar or any(d.tipo_documento in ("modificacion", "aclaracion") for d in documentos)
    if len(documentos) < 2:
        avisos.append(f"sin_documentos_para_comparar: {len(documentos)}")
    return ResultadoHerramienta(
        herramienta="comparar_versiones", evento_id=params.evento_id,
        fragmentos=busqueda.fragmentos, documentos=documentos,
        abstener=not busqueda.suficiente or len(documentos) < 2,
        needs_human_review=revisar,
        coverage_status="parcial" if parcial else "sin_faltantes_detectados",
        warnings=avisos, error=None)


def extraer_requisitos(ctx, params: ExtraerRequisitosParams, recuperador: Recuperador,
                       cliente_jev: ClienteJev | None = None) -> ResultadoHerramienta:
    """Reúne requisitos y fechas; compara actividades sin decidir la vigencia documental."""
    consultas = ([(params.categoria, CONSULTAS_POR_CATEGORIA[params.categoria])]
                 if params.categoria is not None else list(CONSULTAS_POR_CATEGORIA.items()))
    resultados, categorias = [], {}
    for categoria, consulta in [*consultas, (None, CONSULTA_CRONOGRAMA)]:
        try:
            crudo = recuperador.buscar(ctx, params.evento_id, consulta, variante="mejorada", k=5)
        except Exception:
            return _fallo("extraer_requisitos", params.evento_id, "falla_recuperacion")
        try:
            resultados.append(ResultadoBusqueda.model_validate(crudo))
        except ValidationError:
            return _fallo("extraer_requisitos", params.evento_id, "contrato_invalido")
        if categoria is not None:
            for fragmento in resultados[-1].fragmentos:
                categorias.setdefault(fragmento.chunk_id, categoria)

    fragmentos, alertas = {}, {}
    for resultado in resultados:
        for fragmento in resultado.fragmentos:
            fragmentos.setdefault(fragmento.chunk_id, fragmento)
        for alerta in resultado.alertas:
            alertas.setdefault((alerta.tipo, alerta.doc_id), alerta)
    revisar, parcial, avisos = _interpretar(list(alertas.values()))
    abstener = not any(r.suficiente for r in resultados) or not fragmentos

    fechas, candidatas = [], {}
    for fragmento in fragmentos.values():
        for literal, fecha, posicion in encontrar_fechas(fragmento.texto):
            identificador = f"c{len(fechas)}"
            fechas.append(FechaCandidata(
                chunk_id=fragmento.chunk_id, doc_id=fragmento.doc_id,
                tipo_documento=fragmento.tipo_documento, pagina=fragmento.pagina_inicio,
                literal=literal, fecha=fecha))
            if len(candidatas) < MAX_CANDIDATAS_JEV:
                # Compactar espacios conserva contexto útil en las tablas extraídas del PDF.
                antes = re.sub(r"\s+", " ", fragmento.texto[:posicion])[-150:]
                despues = re.sub(r"\s+", " ", fragmento.texto[posicion + len(literal):])[:150]
                candidatas[identificador] = {
                    "seccion": fragmento.seccion,
                    "pasaje": antes + literal + despues,
                    "fecha": literal,
                }

    if fechas and (cliente_jev is None or abstener):
        avisos.append(f"fechas_no_verificadas: {len(fechas)}")
    elif fechas:
        sobrantes = len(fechas) - len(candidatas)
        if sobrantes:
            avisos.append(f"candidatas_sin_verificar: {sobrantes}")
            revisar = True
        preguntas = preguntas_fechas(candidatas)
        try:
            respuesta = validar_respuesta(
                cliente_jev.preguntar({"candidatas": candidatas}, preguntas), preguntas)
            verificadas = []
            for indice, identificador in enumerate(candidatas):
                eleccion = respuesta.respuestas[f"actividad_{identificador}"]
                actividad = eleccion["choice"]
                prob_actividad = eleccion["probabilities"][actividad]
                prob_respaldo = respuesta.respuestas[f"respaldo_{identificador}"]["noul"]
                confianza = min(prob_actividad, prob_respaldo)
                if actividad == "ninguna" and prob_actividad >= CHOICE_MIN:
                    estado = "fuera_del_cronograma"
                elif (actividad != "ninguna" and confianza >= CHOICE_MIN
                      and prob_respaldo >= NOUL_SI):
                    estado = "verificada"
                else:
                    estado = "no_verificada"
                    revisar = True
                verificadas.append(FechaCandidata(
                    **{**fechas[indice].model_dump(), "actividad": actividad, "estado": estado,
                       "prob_actividad": prob_actividad, "prob_respaldo": prob_respaldo}))
            fechas = verificadas + fechas[len(candidatas):]
        except (FallaJev, TimeoutError, ValidationError):
            avisos.append("jev_no_disponible")
            revisar = True

    por_actividad = {}
    for fecha in fechas:
        if fecha.estado == "verificada":
            por_actividad.setdefault(fecha.actividad, set()).add(fecha.fecha)
    for actividad, valores in por_actividad.items():
        if len(valores) > 1:
            revisar = True
            avisos.append(f"fechas_distintas: {actividad}")
    return ResultadoHerramienta(
        herramienta="extraer_requisitos", evento_id=params.evento_id,
        fragmentos=list(fragmentos.values()), fechas=fechas, categorias=categorias,
        abstener=abstener,
        needs_human_review=revisar,
        coverage_status="parcial" if parcial else "sin_faltantes_detectados",
        warnings=avisos, error=None)
