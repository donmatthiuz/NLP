"""Experimento de adopción de JEV en las fechas de la lista: reglas, JEV o no verificar.

La regla de adopción está en docs/consulta/delegacion/F7b_jev_en_fechas.md y se fijó antes de correr.
Todo corre sin red salvo `correr` con --confirmar-envio. Las salidas crudas van a data/.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import obtener_configuracion
from .experimento import mcnemar_p, wilson
from .fechas_reglas import asignar_por_reglas, estado_por_reglas, huella_palabras_clave, texto_para_reglas  # noqa: F401
from .herramientas import armar_candidatas, extraer_requisitos
from .lectura import es_tabla
from .jev import ClienteJevSdk, FallaJev, RespuestaJev, validar_respuesta
from .lista import parametros_propuesta
from .preguntas_jev import ACTIVIDADES_CRONOGRAMA, CHOICE_MIN, MAX_CANDIDATAS_JEV, NOUL_SI, VERSION_PREGUNTAS, preguntas_fechas
from .requisitos import encontrar_fechas

RAIZ = Path(__file__).resolve().parents[3]
AGENTES = RAIZ / "data/consulta/agentes"
EXPERIMENTOS = RAIZ / "data/consulta/experimentos"
PARTICIONES = {"desarrollo": ("399", "363"), "prueba": ("368", "327", "222")}
NUMERO_EVENTO = {"399": "399-IGSS-2026", "363": "363-IGSS-2026", "368": "368-IGSS-2026",
                 "327": "327-IGSS-2023", "222": "222-IGSS-2023"}
CONFLICTOS_222 = ("adquirir_documentos", "recepcion_ofertas")
ALFA = 0.05

def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _leer(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _local(identificador: str) -> str:
    return identificador.split("-", 1)[1]


# --- Variante de reglas ----------------------------------------------------------------

def estados_reglas(candidatas: list, tablas: dict) -> dict:
    """`tablas` dice, por id, si el fragmento de origen es tabla (viene del mapa, no del ciego)."""
    return {fila["id"]: estado_por_reglas(fila["pasaje"], fila["fecha"], tablas.get(fila["id"], False))
            for fila in candidatas}


# --- Exportación -------------------------------------------------------------------------

def candidatas_evento(ctx, numero: str, recuperador) -> list:
    """Todas las fechas que produce extraer_requisitos en el evento, con el pasaje que se le pregunta a JEV."""
    evento_id = recuperador.resolver_evento(ctx, NUMERO_EVENTO[numero])
    if evento_id is None:
        raise SystemExit(f"Evento {NUMERO_EVENTO[numero]} no encontrado")
    resultado = extraer_requisitos(ctx, parametros_propuesta(evento_id), recuperador)
    if resultado.error:
        raise SystemExit(f"extraer_requisitos falló en {numero}: {resultado.error}")
    fechas, candidatas = armar_candidatas(resultado.fragmentos)
    tablas = {f.chunk_id: es_tabla(f.texto) for f in resultado.fragmentos}
    # Si extraer_requisitos se abstiene, la propuesta no le pregunta nada a JEV.
    verifica = not resultado.abstener
    filas = []
    for indice, (local, datos) in enumerate(candidatas.items()):
        filas.append({"id": f"{numero}-{local}", "evento": NUMERO_EVENTO[numero], "fecha": datos["fecha"],
                      "fecha_iso": fechas[indice].fecha.isoformat(), "pasaje": datos["pasaje"],
                      "seccion": datos["seccion"], "chunk_id": fechas[indice].chunk_id,
                      "pagina": fechas[indice].pagina, "tabla": tablas[fechas[indice].chunk_id],
                      "en_propuesta": verifica})
    return filas


def exportar(particion: str, filas: list, directorio: Path = AGENTES) -> dict:
    ciego = [{campo: fila[campo] for campo in ("id", "evento", "fecha", "pasaje", "seccion")} for fila in filas]
    mapa = {fila["id"]: {campo: fila[campo] for campo in ("evento", "chunk_id", "pagina", "fecha_iso", "tabla", "en_propuesta")}
            for fila in filas}
    rutas = {"ciego": directorio / f"fechas_ciego_{particion}.json", "mapa": directorio / f"fechas_mapa_{particion}.json"}
    _escribir(rutas["ciego"], ciego)
    _escribir(rutas["mapa"], mapa)
    return rutas


# --- Corrida con JEV ---------------------------------------------------------------------

def _lotes(candidatas: list) -> list:
    """Hasta 20 candidatas por solicitud y evento: el tope de la propuesta, repetido hasta cubrirlas todas."""
    lotes = []
    for evento in dict.fromkeys(_local_evento(c["id"]) for c in candidatas):
        propias = [c for c in candidatas if _local_evento(c["id"]) == evento]
        for inicio in range(0, len(propias), MAX_CANDIDATAS_JEV):
            lotes.append((evento, propias[inicio:inicio + MAX_CANDIDATAS_JEV]))
    return lotes


def _local_evento(identificador: str) -> str:
    return identificador.split("-", 1)[0]


def correr(candidatas: list, *, cliente_jev, confirmar: bool = False, repetida: bool = False) -> dict:
    lotes = _lotes(candidatas)
    solicitudes = [{"candidatas": {_local(c["id"]): {"seccion": c["seccion"], "pasaje": c["pasaje"], "fecha": c["fecha"]}
                                   for c in filas}} for _, filas in lotes]
    preguntas = [preguntas_fechas(s["candidatas"]) for s in solicitudes]
    if not confirmar:
        return {"lotes": [{"evento": evento, "ids": [c["id"] for c in filas]} for evento, filas in lotes],
                "states": solicitudes, "questions": preguntas}
    registros = []
    for (evento, filas), solicitud, pregunta in zip(lotes, solicitudes, preguntas):
        inicio = time.monotonic()
        respuesta, error = None, None
        try:
            respuesta = cliente_jev.preguntar(solicitud, pregunta).model_dump(mode="json")
        except FallaJev as falla:
            error = falla.codigo
        registros.append({"evento": evento, "ids": [c["id"] for c in filas], "respuesta": respuesta, "error": error,
                          "latencia_ms": (time.monotonic() - inicio) * 1000})
    # Una segunda corrida de prueba ya vio resultados: no es limpia y comparar no emite veredicto con ella.
    return {"limpia": all(r["error"] is None for r in registros) and not repetida, "repetida": repetida,
            "version_preguntas": VERSION_PREGUNTAS,
            "lotes": registros}


def estados_jev(corrida: dict) -> dict:
    """Los estados que la propuesta le daría a cada fecha con esas respuestas (mismos umbrales que herramientas.py)."""
    estados = {}
    for lote in corrida["lotes"]:
        sin_verificar = {"estado": "no_verificada", "actividad": None}
        respuesta = None
        if lote.get("respuesta") is not None:
            respuesta = RespuestaJev.model_validate(lote["respuesta"])
            try:
                validar_respuesta(respuesta, preguntas_fechas([_local(i) for i in lote["ids"]]))
            except Exception:
                respuesta = None
        for identificador in lote["ids"]:
            if respuesta is None:
                estados[identificador] = dict(sin_verificar)
                continue
            local = _local(identificador)
            eleccion = respuesta.respuestas[f"actividad_{local}"]
            actividad = eleccion["choice"]
            prob_actividad = eleccion["probabilities"][actividad]
            prob_respaldo = respuesta.respuestas[f"respaldo_{local}"]["noul"]
            if actividad == "ninguna" and prob_actividad >= CHOICE_MIN:
                estados[identificador] = {"estado": "fuera_del_cronograma", "actividad": actividad}
            elif actividad != "ninguna" and min(prob_actividad, prob_respaldo) >= CHOICE_MIN and prob_respaldo >= NOUL_SI:
                estados[identificador] = {"estado": "verificada", "actividad": actividad}
            else:
                estados[identificador] = dict(sin_verificar)
    return estados


# --- Puntuación y veredicto --------------------------------------------------------------

def puntuar(estados: dict, etiquetas: dict) -> dict:
    """Acierto: verificada con la actividad de la etiqueta. Crítico: verificada con otra (incluida `ninguna`)."""
    aciertos, criticos = [], []
    for identificador, etiqueta in etiquetas.items():
        dato = estados[identificador]
        if dato["estado"] == "verificada":
            (aciertos if dato["actividad"] == etiqueta else criticos).append(identificador)
    n = len(etiquetas)
    por_estado = [estados[i]["estado"] for i in etiquetas]
    return {"n": n, "aciertos": len(aciertos), "criticos": len(criticos),
            "no_verificadas": por_estado.count("no_verificada"),
            "fuera_del_cronograma": por_estado.count("fuera_del_cronograma"),
            "wilson_aciertos": wilson(len(aciertos), n), "ids_aciertos": sorted(aciertos), "ids_criticos": sorted(criticos)}


def mcnemar_aciertos(jev: dict, reglas: dict) -> dict:
    a, b = set(jev["ids_aciertos"]), set(reglas["ids_aciertos"])
    solo_jev, solo_reglas = len(a - b), len(b - a)
    return {"b_solo_jev": solo_jev, "c_solo_reglas": solo_reglas, "p": mcnemar_p(solo_jev, solo_reglas)}


def conflictos(candidatas: list, estados: dict, numero: str) -> list:
    """Actividades con más de una fecha distinta entre las verificadas del evento: lo que la lista avisa como fechas_distintas."""
    por_actividad = {}
    for fila in candidatas:
        dato = estados.get(fila["id"])
        if _local_evento(fila["id"]) == numero and dato and dato["estado"] == "verificada":
            fecha = encontrar_fechas(fila["fecha"])[0][1] if encontrar_fechas(fila["fecha"]) else fila["fecha"]
            por_actividad.setdefault(dato["actividad"], set()).add(fecha)
    return sorted(a for a, fechas in por_actividad.items() if len(fechas) > 1)


def veredicto_sin_jev(reglas: dict, etiquetas: dict) -> dict | None:
    """Veredicto cuando ni el mejor JEV posible alcanzaría p < 0,05 contra reglas sin críticos; None si aún depende de JEV."""
    if reglas["criticos"] != 0:
        return None
    acertadas = set(reglas["ids_aciertos"])
    b_max = sum(1 for i, etiqueta in etiquetas.items() if etiqueta != "ninguna" and i not in acertadas)
    p_minimo = mcnemar_p(b_max, 0)
    if p_minimo < ALFA:
        return None
    return {"decision": "reglas", "motivo": f"JEV no puede superar a las reglas con estos datos (b máximo {b_max}, p mínimo {p_minimo:.3g}) "
            "y las reglas no tienen críticos", "criticos_no_aumentan": True, "significativo_a_favor": False, "p": p_minimo}


def veredicto(jev: dict, reglas: dict, p: float) -> dict:
    """La regla fijada antes de correr: JEV se queda si no tiene más críticos y gana en aciertos con p < 0,05."""
    criticos_ok = jev["criticos"] <= reglas["criticos"]
    gana = jev["aciertos"] > reglas["aciertos"] and p < ALFA
    if criticos_ok and gana:
        decision, motivo = "jev", "JEV no tiene más críticos que las reglas y gana en aciertos con p < 0,05"
    elif jev["criticos"] == 0 and reglas["criticos"] >= 1 and jev["aciertos"] >= 1:
        # Aclaración del 18 de noviembre: un crítico pesa más que una fecha sin verificar, si JEV acierta algo.
        decision, motivo = "jev", "JEV no tiene críticos, acierta al menos una y las reglas tienen críticos: un crítico pesa más que una fecha sin verificar"
    elif jev["criticos"] == 0 and reglas["criticos"] >= 1:
        decision, motivo = "no_verificar", "JEV no tiene críticos pero tampoco aciertos y las reglas tienen críticos: fechas sin verificar"
    elif reglas["criticos"] == 0:
        decision, motivo = "reglas", "JEV no cumple la regla y las reglas no tienen críticos"
    else:
        decision, motivo = "no_verificar", "JEV no cumple la regla y las dos variantes tienen críticos: fechas sin verificar"
    return {"decision": decision, "motivo": motivo, "criticos_no_aumentan": criticos_ok,
            "significativo_a_favor": gana, "p": p}


# --- CLI ---------------------------------------------------------------------------------

def _candidatas_exportadas(particion: str) -> list:
    ruta = AGENTES / f"fechas_ciego_{particion}.json"
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}: corre make fechas-preparar")
    return _leer(ruta)


def _etiquetas(particion: str, candidatas: list) -> dict:
    ruta = AGENTES / f"etiquetas_fechas_{particion}.json"
    if not ruta.exists():
        raise SystemExit(f"Faltan las etiquetas {ruta}")
    etiquetas = _leer(ruta)
    faltan = [c["id"] for c in candidatas if c["id"] not in etiquetas]
    if faltan:
        raise SystemExit(f"Sin etiqueta: {faltan[:5]}{'...' if len(faltan) > 5 else ''}")
    desconocidas = sorted(set(etiquetas) - {c["id"] for c in candidatas})
    if desconocidas:
        raise SystemExit(f"Etiquetas de candidatas inexistentes: {desconocidas[:5]}")
    for identificador, actividad in etiquetas.items():
        if actividad not in ACTIVIDADES_CRONOGRAMA:
            raise SystemExit(f"Actividad desconocida en {identificador}: {actividad}")
    return etiquetas


def _cmd_preparar(opciones) -> int:
    # Importación tardía: el recuperador arrastra psycopg y los modelos.
    from licigt.recuperacion import busqueda
    from licigt.recuperacion.busqueda import Contexto
    ctx = Contexto(tenant_id="empresa_demo", usuario="demo")
    for particion, numeros in PARTICIONES.items():
        filas = [f for numero in numeros for f in candidatas_evento(ctx, numero, busqueda)]
        rutas = exportar(particion, filas)
        por_evento = {n: sum(1 for f in filas if f["id"].startswith(f"{n}-")) for n in numeros}
        print(f"{particion}: {len(filas)} candidatas {por_evento} -> {rutas['ciego']}")
        if len(filas) < 15:
            print(f"AVISO: la partición {particion} tiene menos de 15 candidatas")
    return 0


def hay_corrida_previa(conjunto: str) -> bool:
    return conjunto == "prueba" and any(EXPERIMENTOS.glob(f"fechas_{conjunto}_*.json"))


def _mapa(conjunto: str) -> dict:
    ruta = AGENTES / f"fechas_mapa_{conjunto}.json"
    if not ruta.exists():
        raise SystemExit(f"Falta {ruta}: corre make fechas-preparar")
    return _leer(ruta)


def _cmd_reglas(opciones) -> int:
    candidatas = _candidatas_exportadas(opciones.conjunto)
    estados = estados_reglas(candidatas, {i: d["tabla"] for i, d in _mapa(opciones.conjunto).items()})
    asignadas = sum(1 for e in estados.values() if e["estado"] == "verificada")
    print(f"Reglas en {opciones.conjunto}: {asignadas} verificadas de {len(candidatas)}")
    if opciones.detalle and opciones.conjunto == "desarrollo":
        for fila in candidatas:
            print(f"{fila['id']}\t{estados[fila['id']]['actividad']}\t{fila['seccion'][:30]}\t{fila['pasaje']}")
    # Las reglas se ajustan solo con desarrollo: la prueba se puntúa una vez, en `comparar`.
    ruta = AGENTES / f"etiquetas_fechas_{opciones.conjunto}.json"
    if opciones.conjunto == "desarrollo" and ruta.exists():
        puntos = puntuar(estados, _etiquetas(opciones.conjunto, candidatas))
        print({k: puntos[k] for k in ("n", "aciertos", "criticos", "no_verificadas")})
    return 0


def _cmd_correr(opciones) -> int:
    candidatas = _candidatas_exportadas(opciones.conjunto)
    # Solo las de eventos donde la propuesta verifica (no se abstiene); las demás se reportan aparte.
    mapa = _mapa(opciones.conjunto)
    enviadas = [c for c in candidatas if mapa[c["id"]]["en_propuesta"]]
    if not opciones.confirmar_envio:
        vista = correr(enviadas, cliente_jev=None)
        print(f"Sin envío: {len(vista['lotes'])} solicitudes, {len(enviadas)} candidatas "
              f"({len(candidatas) - len(enviadas)} fuera del tope de la propuesta), versión de preguntas {VERSION_PREGUNTAS}.")
        print(json.dumps({"questions": vista["questions"][0]}, ensure_ascii=False, indent=2))
        return 0
    repetida = hay_corrida_previa(opciones.conjunto)
    if repetida and not opciones.repetir:
        print("Ya hay una corrida de prueba: repetirla la deja sin veredicto y la decisión es del usuario. "
              "Para forzarla, REPETIR=1 (queda marcada como repetida y no limpia).")
        return 1
    if repetida:
        print("AVISO: ya hay una corrida de prueba; esta queda repetida, no limpia, y no dará veredicto.")
    try:
        cliente = ClienteJevSdk(obtener_configuracion())
    except FallaJev as falla:
        print(f"Experimento no iniciado: {falla.codigo}")
        return 1
    try:
        corrida = correr(enviadas, cliente_jev=cliente, confirmar=True, repetida=repetida)
    finally:
        cliente.cerrar()
    corrida["conjunto"] = opciones.conjunto
    ruta = EXPERIMENTOS / f"fechas_{opciones.conjunto}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    _escribir(ruta, corrida)
    print(f"Registro: {ruta}")
    return 0


def _problemas_corrida(corrida: dict, esperados: set) -> list:
    problemas = []
    if not corrida.get("limpia"):
        problemas.append("la corrida no es limpia (error, o una segunda corrida de prueba)")
    if corrida.get("version_preguntas") != VERSION_PREGUNTAS:
        problemas.append(f"versión de preguntas {corrida.get('version_preguntas')} distinta de {VERSION_PREGUNTAS}")
    if any(lote.get("error") for lote in corrida.get("lotes", [])):
        problemas.append("hay lotes en error")
    ids = {i for lote in corrida.get("lotes", []) for i in lote["ids"]}
    if ids != esperados:
        problemas.append("los ids de la corrida no son los del ciego vigente")
    return problemas


def comparar(conjunto: str) -> dict:
    """Puntúa reglas y JEV y emite el veredicto; sin él (y dice por qué) si la corrida no es válida."""
    candidatas = _candidatas_exportadas(conjunto)
    etiquetas = _etiquetas(conjunto, candidatas)
    mapa = _mapa(conjunto)
    estados = {"reglas": estados_reglas(candidatas, {i: d["tabla"] for i, d in mapa.items()})}
    puntos = {"reglas": puntuar(estados["reglas"], etiquetas)}
    salida = {"candidatas": candidatas, "etiquetas": etiquetas, "estados": estados, "puntos": puntos,
              "problemas": [], "veredicto": None, "prueba": None, "corrida": None, "sin_verificar_por_tope": 0}
    esperados = {c["id"] for c in candidatas if mapa[c["id"]]["en_propuesta"]}
    salida["sin_verificar_por_tope"] = len(candidatas) - len(esperados)
    salida["huella_reglas"] = huella_palabras_clave()
    sin_jev = veredicto_sin_jev(puntos["reglas"], etiquetas)
    if sin_jev:
        salida["veredicto"] = {**sin_jev, "huella_reglas": salida["huella_reglas"]}
        return salida
    archivos = sorted(EXPERIMENTOS.glob(f"fechas_{conjunto}_*.json"))
    if not archivos:
        salida["problemas"].append(f"no hay corridas de JEV de {conjunto} y el veredicto aún depende de ellas")
        return salida
    corrida = salida["corrida"] = _leer(archivos[-1])
    salida["archivo"] = archivos[-1].name
    salida["problemas"] = _problemas_corrida(corrida, esperados)
    if salida["problemas"]:
        return salida
    # Las fuera del tope no se le preguntan a JEV: en la propuesta quedan sin verificar.
    por_jev = estados_jev(corrida)
    estados["jev"] = {c["id"]: por_jev.get(c["id"], {"estado": "no_verificada", "actividad": None}) for c in candidatas}
    puntos["jev"] = puntuar(estados["jev"], etiquetas)
    salida["prueba"] = mcnemar_aciertos(puntos["jev"], puntos["reglas"])
    salida["veredicto"] = {**veredicto(puntos["jev"], puntos["reglas"], salida["prueba"]["p"]),
                           "huella_reglas": salida["huella_reglas"]}
    return salida


def _cmd_comparar(opciones) -> int:
    r = comparar(opciones.conjunto)
    candidatas, etiquetas, puntos, estados = r["candidatas"], r["etiquetas"], r["puntos"], r["estados"]
    print(f"{opciones.conjunto}: {len(candidatas)} candidatas, {r['sin_verificar_por_tope']} fuera del tope de la propuesta")
    for nombre, dato in puntos.items():
        bajo, alto = dato["wilson_aciertos"]
        print(f"{nombre}: aciertos {dato['aciertos']} (Wilson {bajo:.3f} a {alto:.3f}), críticos {dato['criticos']}, "
              f"no_verificada {dato['no_verificadas']}, fuera_del_cronograma {dato['fuera_del_cronograma']}")
    if r["prueba"]:
        print(f"McNemar JEV contra reglas: b (solo JEV) = {r['prueba']['b_solo_jev']}, "
              f"c (solo reglas) = {r['prueba']['c_solo_reglas']}, p = {r['prueba']['p']:.4g}")
    if "222" in PARTICIONES[opciones.conjunto]:
        oro = {i: {"estado": "verificada", "actividad": a} for i, a in etiquetas.items() if a != "ninguna"}
        print(f"Conflictos en 222 con las etiquetas de oro: {conflictos(candidatas, oro, '222')}")
        for nombre, dato in estados.items():
            encontrados = conflictos(candidatas, dato, "222")
            print(f"{nombre}: conflictos {encontrados}; detecta los dos conocidos: "
                  f"{all(a in encontrados for a in CONFLICTOS_222)}")
    if r["corrida"]:
        latencias = sorted(l["latencia_ms"] for l in r["corrida"]["lotes"] if l.get("latencia_ms") is not None)
        if latencias:
            print(f"Latencia de JEV por solicitud: mediana {latencias[len(latencias) // 2]:.0f} ms, máximo {latencias[-1]:.0f} ms")
    if r["problemas"]:
        print("Sin veredicto: " + "; ".join(r["problemas"]))
    elif r["veredicto"]:
        print(f"Veredicto: {r['veredicto']['decision']} ({r['veredicto']['motivo']})")
        print(f"Huella de las palabras clave de las reglas: {r['huella_reglas']}")
    return 0


def main(argumentos=None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    orden = analizador.add_subparsers(dest="orden", required=True)
    orden.add_parser("preparar", help="exporta las candidatas por partición (requiere la base)")
    reglas = orden.add_parser("reglas", help="aplica la variante de reglas, sin JEV")
    reglas.add_argument("conjunto", choices=tuple(PARTICIONES))
    reglas.add_argument("--detalle", action="store_true")
    ejecutar = orden.add_parser("correr")
    ejecutar.add_argument("conjunto", choices=tuple(PARTICIONES))
    ejecutar.add_argument("--confirmar-envio", action="store_true")
    ejecutar.add_argument("--repetir", action="store_true", help="fuerza una segunda corrida de prueba (no limpia)")
    comparar = orden.add_parser("comparar")
    comparar.add_argument("conjunto", choices=tuple(PARTICIONES))
    opciones = analizador.parse_args(argumentos)
    return {"preparar": _cmd_preparar, "reglas": _cmd_reglas, "correr": _cmd_correr,
            "comparar": _cmd_comparar}[opciones.orden](opciones)


if __name__ == "__main__":
    raise SystemExit(main())
