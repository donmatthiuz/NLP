"""Flujo de consulta con una herramienta, una regeneración y auditoría en toda salida."""

import inspect
import json
import re
import time
from datetime import datetime, timezone

from pydantic import ValidationError

from .citas_jev import aplicar_citas, citas_activas
from .config import obtener_configuracion_llm
from .decision import decidir
from .esquemas import (
    BuscarDocumentosParams, CompararVersionesParams, ExtraerRequisitosParams,
    RespuestaEstructurada, TEXTO_ABSTENCION, TEXTO_ACLARACION,
)
from .generacion import VERSION_PROMPT, construir_prompt
from .herramientas import buscar_documentos, comparar_versiones, extraer_requisitos, tema_comparacion
from .lectura import ResultadoBusqueda
from .llm import FallaGenerador
from .presupuesto import LimiteAgotado, Presupuesto
from .requisitos import encontrar_fechas
from .validacion import MARCADOR, VIGENCIA, _con_mes, normalizar_cita, validar


# Otras formas de decir que una fecha o cláusula cambió o rige, además de VIGENCIA (que ya cubre "vigente", "sin efecto"…).
SENAL_VIGENCIA = re.compile(r"\b(?:modific|aclarac|aclarad|cambi|rige|actual|aplica|vigor|amend|in force|govern)")


class _RecuperadorObservado:
    """Retiene alertas para F4 porque ResultadoHerramienta solo conserva sus efectos."""
    def __init__(self, recuperador, evento_id):
        self.recuperador = recuperador
        self.evento_id = evento_id
        self.evento_distinto = False
        self.busquedas = []

    def _comprobar_evento(self, crudo):
        if (isinstance(crudo, dict) and isinstance(crudo.get("evento_id"), str)
                and crudo["evento_id"] != self.evento_id):
            self.evento_distinto = True
            raise ValueError("evento_distinto")

    def buscar(self, *args, **kwargs):
        crudo = self.recuperador.buscar(*args, **kwargs)
        self._comprobar_evento(crudo)
        self.busquedas.append(crudo)
        return crudo

    def comparar_versiones(self, *args, **kwargs):
        crudo = self.recuperador.comparar_versiones(*args, **kwargs)
        self._comprobar_evento(crudo)
        return crudo


def _evidencia(resultado):
    fragmentos = {}
    if resultado.herramienta == "comparar_versiones":
        for documento in resultado.documentos:
            for f in documento.fragmentos:
                fragmentos.setdefault(f.chunk_id, f)
    for f in resultado.fragmentos:
        fragmentos.setdefault(f.chunk_id, f)
    valores = list(fragmentos.values())
    if resultado.herramienta == "comparar_versiones":
        documentos = list(dict.fromkeys(f.doc_id for f in valores))
        tipos = {f.doc_id: f.tipo_documento for f in valores}
        orden = {"bases": 0, "aclaracion": 1, "modificacion": 2}
        documentos.sort(key=lambda doc: orden.get(tipos[doc], 3))
        valores.sort(key=lambda f: documentos.index(f.doc_id))
    return valores


def _conflictos(busquedas, fragmentos):
    por_chunk = {f.chunk_id: f.doc_id for f in fragmentos}
    grupos = []
    afectados = set()
    for crudo in busquedas:
        busqueda = ResultadoBusqueda.model_validate(crudo)
        # Solo ids de los fragmentos crudos: descartar uno sospechoso no cambia a qué documento pertenece el afectado.
        for f in busqueda.fragmentos:
            por_chunk.setdefault(f.chunk_id, f.doc_id)
        for alerta in busqueda.alertas:
            if alerta.tipo == "posible_conflicto":
                afectados.update(alerta.chunk_ids_afectados)
                grupo = {alerta.doc_id} | {por_chunk[c] for c in alerta.chunk_ids_afectados if c in por_chunk}
                # Sin ids afectados, conservar ambos lados presentes es la opción prudente.
                if len(grupo) == 1:
                    grupo.update(f.doc_id for f in fragmentos if f.tipo_documento == "bases")
                if grupo not in grupos:
                    grupos.append(grupo)
    return grupos, afectados


def _abstencion(evento_id, resultado=None, aviso=None, herramienta=None, conflicto=False):
    """Revisión humana en una abstención solo si la herramienta trajo un posible_conflicto o un fragmento sospechoso; la vigencia aplica al publicar."""
    avisos = list(resultado.warnings) if resultado else []
    if aviso and aviso not in avisos:
        avisos.append(aviso)
    conflicto = conflicto or any(a.startswith("fragmento_sospechoso:") for a in avisos)
    return RespuestaEstructurada(
        answer=TEXTO_ABSTENCION, sources=[], abstained=True,
        tool_used=resultado.herramienta if resultado else herramienta, evento_id=evento_id,
        needs_human_review=conflicto,
        coverage_status=resultado.coverage_status if resultado else "sin_faltantes_detectados",
        warnings=avisos)


def _atributo_seguro(objeto, nombre):
    try:
        return getattr(objeto, nombre, None)
    except Exception:
        return None


def _con_limites(generador, **limites):
    """Los límites por llamada solo se pasan a un generador que los acepta; uno con la firma del protocolo no los recibe."""
    try:
        parametros = inspect.signature(generador.generar).parameters
    except (TypeError, ValueError):
        return {}
    libre = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parametros.values())
    return {k: v for k, v in limites.items() if v is not None and (libre or k in parametros)}


class _Ejecucion:
    """Lo que la ejecución de una herramienta deja para la auditoría y para quien la llamó."""
    def __init__(self):
        self.resultado, self.fragmentos, self.error, self.validacion = None, [], None, "no_aplica"
        self.citas_jev, self.datos_descartados, self.datos_desde_cita = None, 0, 0
        self.afirmaciones_descartadas = 0
        self.regeneracion_omitida = None


def _ejecutar(ctx, evento_id, evento_salida, pregunta, herramienta, presupuesto, *, recuperador,
              generador, cliente_jev, ejecucion, categoria=None):
    """Ejecuta una herramienta ya elegida, genera y valida; devuelve la respuesta y deja el resto en ejecucion."""
    respuesta = _abstencion(evento_salida)
    resultado, fragmentos, error, validacion = None, [], None, "no_aplica"
    try:
        try:
            config = obtener_configuracion_llm()
        except ValidationError:
            error = "config_llm_invalida"
            respuesta = _abstencion(evento_salida, aviso="generador_no_disponible", herramienta=herramienta)
            return respuesta
        presupuesto.max_segundos = config.presupuesto_segundos
        tope_tokens = config.max_tokens_requisitos if herramienta == "extraer_requisitos" else config.max_tokens
        presupuesto.usar_llamada()
        observado = _RecuperadorObservado(recuperador, evento_id)
        if herramienta == "buscar_documentos":
            params = BuscarDocumentosParams(query=pregunta, evento_id=evento_id)
            resultado = buscar_documentos(ctx, params, observado)
        elif herramienta == "comparar_versiones":
            tema = tema_comparacion(pregunta)
            if not tema:
                respuesta = RespuestaEstructurada(
                    answer=TEXTO_ACLARACION, sources=[], abstained=False, tool_used=None,
                    needs_human_review=False, evento_id=evento_salida, coverage_status="sin_faltantes_detectados",
                    needs_clarification=True, clarification_question=TEXTO_ACLARACION)
                return respuesta
            params = CompararVersionesParams(tema=tema, evento_id=evento_id)
            resultado = comparar_versiones(ctx, params, observado)
        elif herramienta == "extraer_requisitos":
            params = ExtraerRequisitosParams(evento_id=evento_id, categoria=categoria, pregunta=pregunta)
            resultado = extraer_requisitos(ctx, params, observado, cliente_jev=cliente_jev)
        else:
            error = "sin_herramienta"
            return respuesta
        fragmentos = _evidencia(resultado)
        error = resultado.error
        hay_conflicto = lambda: bool(_conflictos(observado.busquedas, fragmentos)[0])
        if observado.evento_distinto:
            error = "evento_distinto"
            respuesta = _abstencion(evento_salida, resultado, "citas_no_validas", conflicto=hay_conflicto())
            validacion = "fallida"
            return respuesta
        if resultado.abstener:
            respuesta = _abstencion(evento_salida, resultado, conflicto=hay_conflicto())
            return respuesta
        if resultado.evento_id != evento_id:
            error = "evento_distinto"
            respuesta = _abstencion(evento_salida, resultado, "citas_no_validas", conflicto=hay_conflicto())
            validacion = "fallida"
            return respuesta

        conflictos, afectados = _conflictos(observado.busquedas, fragmentos)
        # Una comparación necesita preservar los documentos aunque aún no haya alerta.
        protegidos = conflictos
        if herramienta == "comparar_versiones":
            protegidos = [*conflictos, {d.doc_id for d in resultado.documentos}]
        mensajes, evidencia, esquema, avisos = construir_prompt(
            pregunta, fragmentos, fechas=resultado.fechas, conflictos=protegidos,
            chunk_ids_afectados=afectados,
            max_caracteres=config.max_caracteres_evidencia)
        resultado = resultado.model_copy(update={"warnings": list(dict.fromkeys([*resultado.warnings, *avisos]))})
        if not evidencia:
            respuesta = _abstencion(evento_salida, resultado, conflicto=hay_conflicto())
            return respuesta
        informe, cortada = {}, False
        for intento in range(2):
            try:
                # La regeneración cambia la semilla: con temperatura 0 la misma semilla repite la misma salida.
                limites = {"max_tokens": tope_tokens}
                if intento and presupuesto.max_segundos:
                    # Sin esto el peor caso sumaría dos esperas completas; el piso evita una espera inútil.
                    limites["tiempo_espera"] = max(5, presupuesto.max_segundos - (presupuesto.reloj() - presupuesto.inicio))
                antes = presupuesto.reloj()
                try:
                    crudo = generador.generar(mensajes, esquema, semilla_extra=intento,
                                              **_con_limites(generador, **limites))
                finally:
                    duracion = presupuesto.reloj() - antes
                cortada = False
            except FallaGenerador as exc:
                if exc.codigo != "respuesta_cortada":
                    error = exc.codigo
                    respuesta = _abstencion(evento_salida, resultado, "generador_no_disponible", conflicto=hay_conflicto())
                    return respuesta
                cortada = True
            except TimeoutError:
                error = "tiempo_agotado"
                respuesta = _abstencion(evento_salida, resultado, "generador_no_disponible", conflicto=hay_conflicto())
                return respuesta
            except Exception:
                error = "api"
                respuesta = _abstencion(evento_salida, resultado, "generador_no_disponible", conflicto=hay_conflicto())
                return respuesta
            if cortada:
                verificada, crudo = [], None
            else:
                verificada = validar(crudo, evidencia, resultado, evento_id=evento_id, conflictos=conflictos,
                                     informe=informe)
                ejecucion.datos_descartados = informe.get("datos_descartados", 0)
                ejecucion.datos_desde_cita = informe.get("datos_desde_cita", 0)
            if isinstance(verificada, RespuestaEstructurada):
                respuesta = verificada
                validacion = "regenerada_ok" if intento else "ok"
                if citas_activas():
                    respuesta, ejecucion.citas_jev = aplicar_citas(respuesta, fragmentos, cliente_jev)
                return respuesta
            validacion = "fallida"
            # Sin tiempo para otra generación (estimada como la que acaba de terminar, con tope en la regeneración típica medida) no se regenera: se publica lo válido o se abstiene.
            if not intento and not presupuesto.cabe_generacion(min(duracion, config.estimacion_regeneracion_segundos)):
                ejecucion.regeneracion_omitida = "tiempo"
            if intento or ejecucion.regeneracion_omitida:
                parcial = None if cortada else _publicacion_parcial(
                    crudo, verificada, evidencia, resultado, evento_id=evento_id, conflictos=conflictos)
                if parcial:
                    respuesta, ejecucion.afirmaciones_descartadas = parcial
                    validacion = "parcial"
                    if citas_activas():
                        respuesta, ejecucion.citas_jev = aplicar_citas(respuesta, fragmentos, cliente_jev)
                    return respuesta
                break
            try:
                presupuesto.usar_regeneracion()
            except LimiteAgotado:
                break
            if cortada:
                mensajes = [*mensajes, {"role": "user", "content": (
                    "La salida anterior no pasó la validación: respuesta_cortada\n"
                    "la respuesta se cortó: usa como máximo 5 afirmaciones, cada una breve.")}]
                continue
            errores = json.dumps([e.model_dump(exclude_none=True) for e in verificada], ensure_ascii=False)
            desajustes = _desajustes(crudo, verificada)
            # Con cualquier error, no solo falta_segunda_fuente: el segundo intento no debe repetir el mismo hueco.
            alias = _fragmentos_que_faltan(crudo, evidencia, protegidos)
            mensajes = [*mensajes, {"role": "assistant", "content": crudo}, {"role": "user", "content": (
                "La salida anterior no pasó la validación: " + errores + "\n"
                + "".join(f"Desajuste: {d}.\n" for d in desajustes)
                + (f"Fragmentos del documento que falta citar: {', '.join(alias)}. Si ese documento trata el mismo dato, cítalo; si no, abstén.\n" if alias else "") +
                "Corrige esos puntos: copia tramos exactos o elimina la afirmación.\n"
                "- cita_no_literal: copia la cita completa desde el fragmento, sin empezar ni terminar a mitad de una palabra o número.\n"
                "- cita_cruza_filas: la cita no puede abarcar el final de una fila de la tabla y el inicio de la siguiente; copia solo una fila.\n"
                "- esquema_invalido: la cita, con los espacios y saltos de línea colapsados a uno, mide como máximo 500 caracteres; acórtala.\n"
                "- marcador_pegado: cada marcador {n} va solo, entre espacios o antes de . , ; : ), sin letras, dígitos ni símbolos pegados, sin otro marcador contiguo y una sola vez.\n"
                "- dato_no_literal: el literal debe ser un tramo exacto de la cita indicada, sin cambiar ceros ni formato.\n"
                "  Entre dos marcadores solo van ', ', ' y ', ' o ', ' ni ', ' a ', ' al ', ', y ' o ' y el '; un tramo corto (sin palabras de 4 o más letras) con otro texto, ese texto y los dos literales deben aparecer seguidos en la cita; si no, un solo literal.\n"
                "- unidad_fuera_de_literal: la unidad (días, meses, por ciento, mg, Q, US$) va dentro del literal, no junto al marcador.\n"
                "- falta_segunda_fuente: si el otro documento trata el mismo dato, agrega una afirmación con lo que dice ese documento citándolo; si no lo trata, abstén (\"abstener\": true).\n"
                "- afirmacion_duplicada: no repitas una afirmación; cada una dice algo distinto.\n"
                "- cita_ajena: la afirmación debe tratar lo que dice su cita; si la cita no habla de ese dato, quítala.\n"
                "- datos_de_varias_citas: divide en dos afirmaciones, cada una con datos de una sola cita.\n"
                "- dato_fuera_de_literal: quita del texto todo dígito y nombre de mes; ponlo como marcador {n} con su literal en datos. Tampoco escribas letras que parecen cifras (lO, lOO, l.S, S.O).\n"
                '- texto_invalido: usa solo letras latinas, espacios y . , ; : ( ) ¿ ? ¡ ! \" \' - y la barra de y/o, sin saltos de línea ni [n], y cada marcador {n} con su dato y cada dato con su marcador.\n'
                'Si no queda ninguna afirmación respaldada, devuelve "abstener": true.')}]
        if cortada:
            error = "respuesta_cortada"
        respuesta = _abstencion(evento_salida, resultado, "citas_no_validas", conflicto=hay_conflicto())
        return respuesta
    finally:
        ejecucion.resultado, ejecucion.fragmentos = resultado, fragmentos
        ejecucion.error, ejecucion.validacion = error, validacion


def _publicacion_parcial(crudo, errores, evidencia, resultado, *, evento_id, conflictos):
    """Descarta las afirmaciones con error propio y revalida el resto; (respuesta, descartadas) o None.

    Un error de toda la salida (esquema, JSON, evento, segunda fuente de un conflicto) no es descartable: None.
    Si tras descartar falta un documento del grupo en conflicto, validar lo devuelve como falta_segunda_fuente."""
    try:
        salida = json.loads(crudo)
        afirmaciones = salida["afirmaciones"]
        if not isinstance(afirmaciones, list):
            return None
    except (TypeError, ValueError, KeyError):
        return None
    descartadas, con_vigencia = 0, False
    for _ in range(len(afirmaciones)):
        malas = {e.afirmacion for e in errores}
        if None in malas or not all(isinstance(m, int) and 1 <= m <= len(afirmaciones) for m in malas):
            return None
        # Una afirmación descartada que hablaba de vigencia deja la respuesta sin esa parte: lo decide una persona.
        con_vigencia = con_vigencia or any(
            _habla_de_vigencia(a) for i, a in enumerate(afirmaciones, 1) if i in malas)
        afirmaciones = [a for i, a in enumerate(afirmaciones, 1) if i not in malas]
        descartadas += len(malas)
        if not afirmaciones:
            return None
        verificada = validar(json.dumps({**salida, "afirmaciones": afirmaciones}, ensure_ascii=False),
                             evidencia, resultado, evento_id=evento_id, conflictos=conflictos)
        if isinstance(verificada, RespuestaEstructurada):
            if verificada.abstained:
                return None
            avisos = [*verificada.warnings, f"afirmaciones_descartadas: {descartadas}"]
            cambios = {"warnings": avisos}
            if con_vigencia:
                cambios["needs_human_review"] = True
            return verificada.model_copy(update=cambios), descartadas
        errores = verificada
    return None


def _habla_de_vigencia(afirmacion) -> bool:
    """Una afirmación que menciona vigencia o cambio, o que lleva un dato literal de fecha, decide algo que ve una persona."""
    if not isinstance(afirmacion, dict):
        return False
    texto = afirmacion.get("texto")
    if isinstance(texto, str):
        normal = normalizar_cita(texto)
        if VIGENCIA.search(normal) or SENAL_VIGENCIA.search(normal):
            return True
    datos = afirmacion.get("datos")
    return isinstance(datos, list) and any(
        isinstance(d, dict) and isinstance(d.get("literal"), str) and (_con_mes(d["literal"]) or encontrar_fechas(d["literal"]))
        for d in datos)


def _fragmentos_que_faltan(crudo, evidencia, grupos):
    """Alias de la evidencia del documento de un grupo en conflicto que la salida no citó; sin texto de los fragmentos."""
    try:
        citados = {evidencia[c["fragmento"]].doc_id for a in json.loads(crudo)["afirmaciones"] for c in a["citas"]}
    except (TypeError, ValueError, KeyError, AttributeError):
        citados = set()  # salida ilegible: se nombran todos los documentos del grupo
    disponibles = {f.doc_id for f in evidencia.values()}
    faltan = set()
    for grupo in grupos:
        presentes = set(grupo) & disponibles
        if len(presentes) >= 2 and not presentes <= citados:
            faltan |= presentes - citados
    return [alias for alias, f in evidencia.items() if f.doc_id in faltan]


URL_O_CORREO = re.compile(r"https?:|www\.|\S@\S", re.IGNORECASE)


def _desajustes(crudo, errores):
    """Datos y marcadores de cada afirmación con texto_invalido, para decirle al modelo qué no cuadra; sin texto."""
    try:
        afirmaciones = json.loads(crudo)["afirmaciones"]
    except (TypeError, ValueError, KeyError):
        return []
    lineas = []
    for e in errores:
        if e.codigo != "texto_invalido" or e.afirmacion is None or e.afirmacion > len(afirmaciones):
            continue
        try:
            afirmacion = afirmaciones[e.afirmacion - 1]
            datos, marcadores = len(afirmacion["datos"]), len(MARCADOR.findall(afirmacion["texto"]))
        except (TypeError, KeyError):
            continue
        if datos != marcadores:
            lineas.append(f"la afirmación {e.afirmacion} tiene {datos} {'dato' if datos == 1 else 'datos'} y "
                          f"{marcadores} {'marcador' if marcadores == 1 else 'marcadores'}")
        if URL_O_CORREO.search(afirmacion["texto"]):
            lineas.append(f"la afirmación {e.afirmacion} contiene una URL o un correo; "
                          "ponla como dato {n} con su literal o quítala")
    return lineas


def _registrar(auditar, usuario, tenant_id, evento_salida, intencion, respuesta, fragmentos,
               validacion, inicio, error, generador, citas_jev=None, jev_sustituida=None, datos_descartados=0,
               datos_desde_cita=0, afirmaciones_descartadas=0, regeneracion_omitida=None):
    """Evento de auditoría de una consulta; si el registro falla, la respuesta no cambia."""
    try:
        auditar({
            "momento": datetime.now(timezone.utc).isoformat(),
            "usuario": usuario, "tenant_id": tenant_id,
            "evento_id": evento_salida, "intencion": intencion, "herramienta": respuesta.tool_used,
            "chunk_ids": [f.chunk_id for f in fragmentos], "abstained": respuesta.abstained,
            "needs_human_review": respuesta.needs_human_review, "validacion": validacion,
            "latencia_ms": (time.monotonic() - inicio) * 1000, "error": error,
            "chunk_ids_citados": list(dict.fromkeys(f.chunk_id for f in respuesta.sources)),
            "modelo_generador": _atributo_seguro(generador, "modelo_generador"),
            "version_prompt": VERSION_PROMPT,
            **({"citas_jev": citas_jev} if citas_jev else {}),
            **({"herramienta_jev_sustituida": jev_sustituida} if jev_sustituida else {}),
            **({"datos_descartados": datos_descartados} if datos_descartados else {}),
            **({"datos_desde_cita": datos_desde_cita} if datos_desde_cita else {}),
            **({"afirmaciones_descartadas": afirmaciones_descartadas} if afirmaciones_descartadas else {}),
            **({"regeneracion_omitida": regeneracion_omitida} if regeneracion_omitida else {}),
        })
    except Exception:
        pass


def consultar(ctx, evento_id, pregunta, *, enrutador, recuperador, generador,
              cliente_jev=None, auditar=lambda evento: None, reloj=time.monotonic) -> RespuestaEstructurada:
    inicio = time.monotonic()
    usuario = _atributo_seguro(ctx, "usuario")
    tenant_id = _atributo_seguro(ctx, "tenant_id")
    # Incluso un id inválido debe producir una respuesta compatible con TextoNoVacio.
    evento_salida = evento_id if isinstance(evento_id, str) and evento_id.strip() else "sin_evento"
    respuesta = _abstencion(evento_salida)
    resultado, herramienta, error, citas_jev = None, None, None, None
    jev_sustituida, datos_descartados, datos_desde_cita = None, 0, 0
    afirmaciones_descartadas, regeneracion_omitida = 0, None
    fragmentos = []
    intencion = None
    validacion = "no_aplica"
    try:
        presupuesto = Presupuesto(reloj=reloj)
        if evento_salida != evento_id:
            error = "parametros_invalidos"
            return respuesta
        juicios, clasificacion = enrutador.clasificar(pregunta)
        siguiente = decidir(juicios, clasificacion)
        intencion = {"accion": siguiente.accion, "motivo": siguiente.motivo, "variante": clasificacion.variante}
        if siguiente.accion == "abstener":
            return respuesta
        if siguiente.accion == "aclarar":
            respuesta = RespuestaEstructurada(
                answer=siguiente.pregunta_aclaratoria, sources=[], abstained=False, tool_used=None,
                needs_human_review=False, evento_id=evento_salida, coverage_status="sin_faltantes_detectados",
                needs_clarification=True, clarification_question=siguiente.pregunta_aclaratoria)
            return respuesta

        herramienta = siguiente.herramienta
        jev_sustituida = siguiente.herramienta_jev_sustituida
        ejecucion = _Ejecucion()
        try:
            respuesta = _ejecutar(ctx, evento_id, evento_salida, pregunta, herramienta, presupuesto,
                                  recuperador=recuperador, generador=generador, cliente_jev=cliente_jev,
                                  ejecucion=ejecucion)
            return respuesta
        finally:
            resultado, fragmentos = ejecucion.resultado, ejecucion.fragmentos
            error, validacion = ejecucion.error or error, ejecucion.validacion
            citas_jev, datos_descartados = ejecucion.citas_jev, ejecucion.datos_descartados
            datos_desde_cita = ejecucion.datos_desde_cita
            afirmaciones_descartadas = ejecucion.afirmaciones_descartadas
            regeneracion_omitida = ejecucion.regeneracion_omitida
    except LimiteAgotado:
        error = "presupuesto_agotado"
        respuesta = _abstencion(evento_salida, resultado, "citas_no_validas", herramienta)
        return respuesta
    except ValidationError:
        error = "contrato_invalido" if resultado else "parametros_invalidos"
        respuesta = _abstencion(evento_salida, resultado, herramienta=herramienta)
        return respuesta
    except Exception:
        error = "falla_consulta"
        respuesta = _abstencion(evento_salida, resultado, herramienta=herramienta)
        return respuesta
    finally:
        _registrar(auditar, usuario, tenant_id, evento_salida, intencion, respuesta, fragmentos,
                   validacion, inicio, error, generador, citas_jev, jev_sustituida, datos_descartados,
                   datos_desde_cita, afirmaciones_descartadas, regeneracion_omitida)
