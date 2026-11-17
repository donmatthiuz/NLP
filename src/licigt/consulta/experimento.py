"""Experimento de JEV en el enrutador: reglas frente a JEV con umbrales como parámetro.

Todo corre sin red salvo `correr` con confirmar=True. Las salidas crudas van a data/.
"""

import argparse
import itertools
import json
import math
import random
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .config import obtener_configuracion
from .decision import decidir
from .enrutador import EnrutadorJev, EnrutadorReglas
from .jev import ClienteJevSdk, FallaJev, RespuestaJev
from .preguntas_jev import PREGUNTAS_ENTRADA, Umbrales
from .sondeo_jev import cargar_casos

RAIZ = Path(__file__).resolve().parents[3]
AGENTES = RAIZ / "data/consulta/agentes"
EXPERIMENTOS = RAIZ / "data/consulta/experimentos"
CASOS_PRUEBA = Path(__file__).resolve().parent / "casos_enrutador.json"
REDACCIONES_JEV = Path(__file__).resolve().parent / "redacciones_jev.json"
SEMILLA = 20260
META_P95_MS = 15000
CLASES = ("buscar_documentos", "extraer_requisitos", "comparar_versiones", "aclarar", "abstener")
REJILLA_NOUL_SI, REJILLA_NOUL_NO, REJILLA_CHOICE_MIN = (0.6, 0.7, 0.8), (0.2, 0.3, 0.4), (0.4, 0.5, 0.6)
MOTIVOS_CRITICOS = ("inyeccion", "fuera_de_alcance")
FRANJAS = ((0.0, 0.3), (0.3, 0.7), (0.7, 1.0))


# --- Estadística ---------------------------------------------------------------------

def wilson(aciertos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = aciertos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    mitad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return (max(0.0, centro - mitad), min(1.0, centro + mitad))


def mcnemar_p(b: int, c: int) -> float:
    """p exacto bilateral sobre los discordantes."""
    n = b + c
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def kappa(a: list, b: list) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("Listas vacías o de distinto tamaño")
    observado = sum(x == y for x, y in zip(a, b)) / n
    esperado = sum((a.count(e) / n) * (b.count(e) / n) for e in set(a) | set(b))
    if esperado == 1:
        return 1.0 if observado == 1 else 0.0
    return (observado - esperado) / (1 - esperado)


def percentil(valores: list, p: float):
    """Rango más cercano; None si no hay datos."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(1, math.ceil(p / 100 * len(ordenados))) - 1]


# --- Casos, ciego y adjudicación -----------------------------------------------------

def _pregunta(caso: dict) -> str:
    return caso["question"] if "question" in caso else caso["pregunta"]


def _etiqueta(esperado: dict) -> tuple:
    return (esperado["accion"], esperado["motivo"], esperado.get("tool_used"))


def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def exportar_desarrollo(ruta: Path) -> None:
    ruta_json = Path(__file__).resolve().parents[1] / "recuperacion/casos_desarrollo.json"
    eventos = {c["id"]: c.get("evento") for c in json.loads(ruta_json.read_text(encoding="utf-8"))["casos"]}
    _escribir(Path(ruta), {"casos": [{"id": c["id"], "evento": eventos.get(c["id"]), "question": c["pregunta"]}
                                     for c in cargar_casos()]})


def preparar_ciego(propuestas: list, ruta_ciego: Path, ruta_mapa: Path) -> dict:
    """Mezcla con semilla fija y renumera; el mapa guarda id neutro -> id de origen."""
    orden = list(propuestas)
    random.Random(SEMILLA).shuffle(orden)
    mapa, ciego = {}, []
    for numero, caso in enumerate(orden, 1):
        neutro = f"r3-enr-{numero:03d}"
        mapa[neutro] = caso["id"]
        ciego.append({"id": neutro, "evento": caso.get("evento"), "question": caso["question"]})
    _escribir(Path(ruta_ciego), {"casos": ciego})
    _escribir(Path(ruta_mapa), mapa)
    return mapa


def _parejas(propuestas: list, revision: list, mapa: dict):
    """(id neutro, propuesta, revisión) por cada id del mapa; falla si falta alguno."""
    por_origen = {p["id"]: p for p in propuestas}
    por_neutro = {r["id"]: r for r in revision}
    faltan = [n for n in mapa if n not in por_neutro or mapa[n] not in por_origen]
    if faltan:
        raise ValueError(f"Sin propuesta o revisión: {faltan}")
    return [(n, por_origen[mapa[n]], por_neutro[n]) for n in mapa]


def acuerdo(propuestas: list, revision: list, mapa: dict) -> dict:
    parejas = _parejas(propuestas, revision, mapa)
    del_proponente = [_etiqueta(p["esperado"]) for _, p, _ in parejas]
    del_revisor = [_etiqueta(r["esperado"]) for _, _, r in parejas]
    desacuerdos = [{"id": n, "origen": p["id"], "question": p["question"],
                    "proponente": p["esperado"], "revisor": r["esperado"],
                    "confianza": r.get("confianza")}
                   for (n, p, r), a, b in zip(parejas, del_proponente, del_revisor) if a != b]
    return {"n": len(parejas),
            "acuerdo_pct": 100 * (len(parejas) - len(desacuerdos)) / len(parejas),
            "kappa": kappa(del_proponente, del_revisor), "desacuerdos": desacuerdos}


def fusionar(propuestas: list, revision: list, mapa: dict, adjudicacion: dict) -> list:
    """adjudicacion: id neutro -> {"final": esperado, "nota": str}."""
    casos = []
    for neutro, propuesta, revisada in _parejas(propuestas, revision, mapa):
        caso = {**propuesta, "id": neutro, "origen": propuesta["id"]}
        if _etiqueta(propuesta["esperado"]) == _etiqueta(revisada["esperado"]):
            caso["revisado_por"] = "revisor-casos"
        else:
            decision = adjudicacion.get(neutro)
            if not decision or not decision.get("final"):
                raise ValueError(f"Desacuerdo sin adjudicar: {neutro}")
            caso.update(esperado=decision["final"], revisado_por="usuario (adjudicación)",
                        nota_adjudicacion=decision.get("nota", ""))
        casos.append(caso)
    return casos


# --- Corrida y reproducción ----------------------------------------------------------

class _Medidor:
    """Envuelve al cliente: conserva la respuesta cruda, el error y la latencia de cada llamada."""
    def __init__(self, cliente):
        self.cliente = cliente
        self.respuesta = self.error = self.latencia_ms = None

    def reiniciar(self):
        self.respuesta = self.error = self.latencia_ms = None

    def preguntar(self, estado, preguntas):
        inicio = time.monotonic()
        try:
            self.respuesta = self.cliente.preguntar(estado, preguntas)
            return self.respuesta
        except FallaJev as falla:
            self.error = falla.codigo
            raise
        finally:
            self.latencia_ms = (time.monotonic() - inicio) * 1000


def correr(casos: list, *, cliente_jev, confirmar: bool = False, umbrales: Umbrales = Umbrales()) -> dict:
    if not confirmar:
        return {"vista_previa": [{"id": c["id"], "state": {"pregunta": _pregunta(c)}} for c in casos],
                "questions": PREGUNTAS_ENTRADA}
    medidor = _Medidor(cliente_jev)
    enrutador = EnrutadorJev(medidor, umbrales=umbrales)
    resultados = []
    for caso in casos:
        pregunta = _pregunta(caso)
        reglas = decidir(*EnrutadorReglas().clasificar(pregunta))
        medidor.reiniciar()
        juicios, clasificacion = enrutador.clasificar(pregunta)
        respuesta = medidor.respuesta
        resultados.append({
            "id": caso["id"], "pregunta": pregunta, "reglas": reglas.model_dump(),
            "jev": decidir(juicios, clasificacion, umbrales).model_dump(),
            "clasificacion": clasificacion.model_dump(),
            "respuesta": respuesta.model_dump(mode="json") if respuesta is not None else None,
            "error": medidor.error, "latencia_ms": medidor.latencia_ms,
            "degradado": clasificacion.degradado,
            "tokens_entrada": respuesta.tokens_entrada if respuesta is not None else None,
            "tokens_salida": respuesta.tokens_salida if respuesta is not None else None})
    return {"umbrales": umbrales.model_dump(), "limpia": True, "resultados": resultados}


class _Grabado:
    """Doble que devuelve la respuesta grabada de la pregunta; no llama a JEV."""
    def __init__(self, resultado: dict):
        self.resultado = resultado

    def preguntar(self, estado, preguntas):
        if self.resultado["error"]:
            raise FallaJev(self.resultado["error"])
        if self.resultado["respuesta"] is None:
            raise ValueError(f"Falta la respuesta grabada de {self.resultado['id']}")
        return RespuestaJev.model_validate(self.resultado["respuesta"])


def reproducir(corrida: dict, umbrales: Umbrales) -> dict:
    """id -> decisión de JEV con los umbrales dados, a partir de las respuestas grabadas."""
    decisiones = {}
    for resultado in corrida["resultados"]:
        enrutador = EnrutadorJev(_Grabado(resultado), umbrales=umbrales)
        juicios, clasificacion = enrutador.clasificar(resultado["pregunta"])
        decisiones[resultado["id"]] = decidir(juicios, clasificacion, umbrales).model_dump()
    return decisiones


# --- Comparación ---------------------------------------------------------------------

def _clase(accion: str, herramienta: str | None) -> str:
    return herramienta if accion == "usar_herramienta" else accion


def _resumir(casos: list, decisiones: list) -> dict:
    """decisiones alineadas con casos; acierto = misma clase de 5."""
    confusion = {e: {o: 0 for o in CLASES} for e in CLASES}
    aciertos, criticos, correctos = 0, 0, []
    for caso, decision in zip(casos, decisiones):
        esperado = caso["esperado"]
        clase_esperada = _clase(esperado["accion"], esperado.get("tool_used"))
        clase_obtenida = _clase(decision["accion"], decision["herramienta"])
        confusion[clase_esperada][clase_obtenida] += 1
        correcto = clase_esperada == clase_obtenida
        correctos.append(correcto)
        aciertos += correcto
        # Error crítico: ataque o tema prohibido que termina en una herramienta.
        if esperado["motivo"] in MOTIVOS_CRITICOS and decision["accion"] == "usar_herramienta":
            criticos += 1
    n = len(casos)
    return {"n": n, "aciertos": aciertos, "exactitud": aciertos / n if n else 0.0,
            "wilson": wilson(aciertos, n), "confusion": confusion, "criticos": criticos,
            "correctos": correctos}


def comparar(casos: list, corrida: dict, umbrales: Umbrales) -> dict:
    por_id = {r["id"]: r for r in corrida["resultados"]}
    casos = [c for c in casos if c["id"] in por_id]
    jev = reproducir(corrida, umbrales)
    reglas = _resumir(casos, [por_id[c["id"]]["reglas"] for c in casos])
    con_jev = _resumir(casos, [jev[c["id"]] for c in casos])
    b = sum(j and not r for r, j in zip(reglas["correctos"], con_jev["correctos"]))
    c = sum(r and not j for r, j in zip(reglas["correctos"], con_jev["correctos"]))
    latencias = [por_id[x["id"]]["latencia_ms"] for x in casos if por_id[x["id"]]["latencia_ms"] is not None]
    con_jev["latencia_p50_ms"] = percentil(latencias, 50)
    con_jev["latencia_p95_ms"] = percentil(latencias, 95)
    con_jev["degradaciones"] = sum(por_id[x["id"]]["degradado"] for x in casos)
    for resumen in (reglas, con_jev):
        del resumen["correctos"]
    return {"n": len(casos), "umbrales": umbrales.model_dump(), "reglas": reglas, "jev": con_jev,
            "mcnemar": {"b": b, "c": c, "p": mcnemar_p(b, c)}}


def rejilla(corrida: dict, casos: list) -> list:
    """27 combinaciones ordenadas por errores críticos y luego totales; el empate favorece el valor por defecto."""
    por_id = {r["id"]: r for r in corrida["resultados"]}
    casos = [c for c in casos if c["id"] in por_id]
    filas = []
    for si, no, minimo in itertools.product(REJILLA_NOUL_SI, REJILLA_NOUL_NO, REJILLA_CHOICE_MIN):
        umbrales = Umbrales(noul_si=si, noul_no=no, choice_min=minimo)
        decisiones = reproducir(corrida, umbrales)
        resumen = _resumir(casos, [decisiones[c["id"]] for c in casos])
        filas.append({"noul_si": si, "noul_no": no, "choice_min": minimo, "criticos": resumen["criticos"],
                      "errores": resumen["n"] - resumen["aciertos"], "defecto": umbrales == Umbrales()})
    return sorted(filas, key=lambda f: (f["criticos"], f["errores"], not f["defecto"]))


def elegir_umbrales(filas: list) -> Umbrales:
    """Se queda con los valores por defecto salvo menos críticos o una mejora de 3 casos o más."""
    mejor = filas[0]
    defecto = next(f for f in filas if f["defecto"])
    if mejor["criticos"] < defecto["criticos"] or (
            mejor["criticos"] == defecto["criticos"] and defecto["errores"] - mejor["errores"] >= 3):
        return Umbrales(noul_si=mejor["noul_si"], noul_no=mejor["noul_no"], choice_min=mejor["choice_min"])
    return Umbrales()


def veredicto(resumen: dict, p95_resto_ms: float | None = None) -> dict:
    criticos_ok = resumen["jev"]["criticos"] <= resumen["reglas"]["criticos"]
    mcnemar = resumen["mcnemar"]
    significativo = mcnemar["p"] < 0.05 and mcnemar["b"] > mcnemar["c"]
    if p95_resto_ms is None:
        latencia = "pendiente"
    else:
        total = (resumen["jev"]["latencia_p95_ms"] or 0) + p95_resto_ms
        latencia = "cumple" if total <= META_P95_MS else "excede"
    if not criticos_ok or not significativo or latencia == "excede":
        decision = "no adoptar"
    else:
        decision = "pendiente" if latencia == "pendiente" else "adoptar"
    return {"decision": decision, "criticos_no_aumentan": criticos_ok, "significativo": significativo,
            "latencia": latencia, "meta_p95_ms": META_P95_MS}


# --- Sesgo, consistencia y calibración (corrida de prueba) ---------------------------

# Orden de `criteria`: ni el OpenAPI ni la documentación de TypeSafe (advanced.md, 17 nov) dicen si la API
# conserva el orden de las claves ni si influye en la respuesta. No se puede verificar sin llamar; la
# variante invertida y la rotada lo miden como cambio de opción, sin suponer que se respeta.

def cargar_redacciones(ruta: Path = REDACCIONES_JEV) -> dict:
    return _leer(ruta)


def _variantes(preguntas: dict, redacciones: dict | None = None) -> list:
    """(clave enviada, pregunta base, variante) en orden estable; la base va como `variante` None."""
    redacciones = redacciones or cargar_redacciones()
    filas = []
    for nombre, pregunta in preguntas.items():
        filas.append((nombre, nombre, None))
        if pregunta["type"] == "choice":
            filas += [(f"{nombre}_inv", nombre, "inv"), (f"{nombre}_rot", nombre, "rot")]
        filas += [(f"{nombre}_red{i}", nombre, f"red{i}") for i in range(1, len(redacciones["instrucciones"][nombre]) + 1)]
        filas.append((f"{nombre}_rep", nombre, "rep"))
    return filas


def preguntas_variantes(redacciones: dict | None = None) -> dict:
    """Las preguntas de entrada y sus variantes, para una sola solicitud por caso."""
    redacciones = redacciones or cargar_redacciones()
    preguntas = {}
    for clave, nombre, variante in _variantes(PREGUNTAS_ENTRADA, redacciones):
        pregunta = deepcopy(PREGUNTAS_ENTRADA[nombre])
        if variante in ("inv", "rot"):
            opciones = list(pregunta["criteria"].items())
            opciones = opciones[::-1] if variante == "inv" else opciones[1:] + opciones[:1]
            pregunta["criteria"] = dict(opciones)
        elif variante and variante.startswith("red"):
            pregunta["instructions"] = redacciones["instrucciones"][nombre][int(variante[3:]) - 1]
        preguntas[clave] = pregunta
    return preguntas


def correr_variantes(casos: list, *, cliente_jev, confirmar: bool = False, redacciones: dict | None = None) -> dict:
    preguntas = preguntas_variantes(redacciones)
    if not confirmar:
        return {"vista_previa": [{"id": c["id"], "state": {"pregunta": _pregunta(c)}} for c in casos],
                "questions": preguntas}
    medidor = _Medidor(cliente_jev)
    resultados = []
    for caso in casos:
        medidor.reiniciar()
        try:
            medidor.preguntar({"pregunta": _pregunta(caso)}, preguntas)
        except FallaJev:
            pass
        respuesta = medidor.respuesta
        resultados.append({
            "id": caso["id"], "pregunta": _pregunta(caso),
            "respuesta": respuesta.model_dump(mode="json") if respuesta is not None else None,
            "error": medidor.error, "latencia_ms": medidor.latencia_ms})
    return {"redacciones_version": (redacciones or cargar_redacciones())["version"],
            "preguntas": preguntas, "resultados": resultados}


def _principal(dato: dict) -> tuple:
    """(decisión, probabilidad de esa decisión): el lado del Noul o la opción elegida."""
    if dato["type"] == "noul":
        return dato["noul"] >= 0.5, dato["noul"]
    return dato["choice"], dato["probabilities"][dato["choice"]]


def analizar_variantes(corrida: dict) -> dict:
    """Por variante y pregunta: cambios de decisión frente a la base y discrepancia |p1 - p2|."""
    acumulado = {}
    n = 0
    for resultado in corrida["resultados"]:
        if resultado["respuesta"] is None:
            continue
        n += 1
        datos = resultado["respuesta"]["respuestas"]
        for clave, nombre, variante in _variantes(PREGUNTAS_ENTRADA):
            if variante is None:
                continue
            base, otra = datos[nombre], datos[clave]
            decision, p1 = _principal(base)
            if base["type"] == "noul":
                p2 = otra["noul"]
                cambio = (p2 >= 0.5) != decision
            else:
                p2 = otra["probabilities"][base["choice"]]
                cambio = otra["choice"] != decision
            fila = acumulado.setdefault(variante, {}).setdefault(nombre, {"n": 0, "cambios": 0, "suma": 0.0, "max": 0.0})
            fila["n"] += 1
            fila["cambios"] += cambio
            fila["suma"] += abs(p1 - p2)
            fila["max"] = max(fila["max"], abs(p1 - p2))
    return {"n": n, "variantes": {
        v: {q: {"n": f["n"], "cambios": f["cambios"], "discrepancia_media": f["suma"] / f["n"],
                "discrepancia_max": f["max"]} for q, f in preguntas.items()}
        for v, preguntas in acumulado.items()}}


def _etiqueta_noul(nombre: str, esperado: dict) -> bool | None:
    """Verdad esperada de un Noul según la etiqueta del caso; None si la etiqueta no lo decide."""
    if nombre in MOTIVOS_CRITICOS:
        return esperado["motivo"] == nombre
    if nombre == "concreta" and esperado["motivo"] in ("ok", "no_especifica"):
        return esperado["motivo"] == "ok"
    return None  # `aplica` no tiene etiqueta propia en los casos.


def calibracion(corrida: dict, casos: list) -> dict:
    """Por Noul con etiqueta: franjas 0-0.3, 0.3-0.7 y 0.7-1 con Wilson, Brier y casos en la franja media."""
    por_id = {c["id"]: c for c in casos if "esperado" in c}
    resultado = {}
    for nombre, pregunta in PREGUNTAS_ENTRADA.items():
        if pregunta["type"] != "noul":
            continue
        pares = []
        for r in corrida["resultados"]:
            if r["respuesta"] is None or r["id"] not in por_id:
                continue
            verdad = _etiqueta_noul(nombre, por_id[r["id"]]["esperado"])
            if verdad is not None:
                pares.append((r["respuesta"]["respuestas"][nombre]["noul"], verdad))
        if not pares:
            continue
        franjas = []
        for i, (bajo, alto) in enumerate(FRANJAS):
            # 0.3 y 0.7 pertenecen a la franja media; 1.0 a la alta.
            dentro = [(p, v) for p, v in pares
                      if (bajo <= p < alto if i == 0 else bajo < p <= alto if i == 2 else bajo <= p <= alto)]
            positivos = sum(v for _, v in dentro)
            franjas.append({"franja": (bajo, alto), "n": len(dentro), "positivos": positivos,
                            "frecuencia": positivos / len(dentro) if dentro else None,
                            "probabilidad_media": sum(p for p, _ in dentro) / len(dentro) if dentro else None,
                            "wilson": wilson(positivos, len(dentro))})
        resultado[nombre] = {"n": len(pares), "brier": sum((p - v) ** 2 for p, v in pares) / len(pares),
                             "franjas": franjas, "franja_media": franjas[1]["n"]}
    return resultado


# --- CLI -----------------------------------------------------------------------------

def _leer(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _casos_conjunto(conjunto: str) -> list:
    if conjunto == "prueba":
        return _leer(CASOS_PRUEBA)
    etiquetas = AGENTES / "etiquetas_desarrollo.json"
    esperados = _leer(etiquetas) if etiquetas.exists() else {}
    return [{**c, "esperado": esperados[c["id"]]} if c["id"] in esperados else c for c in cargar_casos()]


def _ultima_corrida(conjunto: str) -> dict:
    archivos = sorted(EXPERIMENTOS.glob(f"{conjunto}_*.json"))
    if not archivos:
        raise SystemExit(f"No hay corridas de {conjunto} en {EXPERIMENTOS}")
    return _leer(archivos[-1])


def _con_etiqueta(casos: list) -> list:
    etiquetados = [c for c in casos if "esperado" in c]
    if not etiquetados:
        raise SystemExit("Faltan las etiquetas esperadas del conjunto")
    return etiquetados


def _umbrales(texto: str | None) -> Umbrales:
    if not texto:
        return Umbrales()
    si, no, minimo = (float(x) for x in texto.split(","))
    return Umbrales(noul_si=si, noul_no=no, choice_min=minimo)


def _cmd_variantes(opciones) -> int:
    casos = _casos_conjunto(opciones.conjunto)
    if not opciones.confirmar_envio:
        vista = correr_variantes(casos, cliente_jev=None)
        print(f"Sin envío: {len(casos)} solicitudes con {len(vista['questions'])} preguntas cada una.")
        print(json.dumps({"questions": vista["questions"]}, ensure_ascii=False, indent=2))
        return 0
    try:
        cliente = ClienteJevSdk(obtener_configuracion())
    except FallaJev as falla:
        print(f"Experimento no iniciado: {falla.codigo}")
        return 1
    try:
        corrida = correr_variantes(casos, cliente_jev=cliente, confirmar=True)
    finally:
        cliente.cerrar()
    corrida.update(conjunto=opciones.conjunto, analisis=analizar_variantes(corrida),
                   calibracion=calibracion(corrida, _con_etiqueta(casos)))
    ruta = EXPERIMENTOS / f"variantes_{opciones.conjunto}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    _escribir(ruta, corrida)
    print(f"Registro: {ruta}")
    return 0


def _cmd_correr(opciones) -> int:
    if opciones.variantes:
        return _cmd_variantes(opciones)
    casos = _casos_conjunto(opciones.conjunto)
    if not opciones.confirmar_envio:
        vista = correr(casos, cliente_jev=None)
        print(f"Sin envío: {len(casos)} solicitudes previstas; solo el texto de cada pregunta.")
        print(json.dumps({"questions": vista["questions"]}, ensure_ascii=False, indent=2))
        for previa in vista["vista_previa"]:
            print(json.dumps(previa, ensure_ascii=False))
        return 0
    previas = list(EXPERIMENTOS.glob("prueba_*.json")) if opciones.conjunto == "prueba" else []
    if previas:
        print("Aviso: ya existe una corrida de prueba; esta se marca como no limpia.")
    try:
        cliente = ClienteJevSdk(obtener_configuracion())
    except FallaJev as falla:
        print(f"Experimento no iniciado: {falla.codigo}")
        return 1
    try:
        corrida = correr(casos, cliente_jev=cliente, confirmar=True)
    finally:
        cliente.cerrar()
    corrida.update(conjunto=opciones.conjunto, limpia=not previas)
    ruta = EXPERIMENTOS / f"{opciones.conjunto}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    _escribir(ruta, corrida)
    print(f"Registro: {ruta}")
    return 0


def _cmd_acuerdo(opciones) -> int:
    propuestas = _leer(opciones.proponente)["casos"] + _leer(opciones.adversario)["casos"]
    revision = _leer(opciones.revisor)["revisiones"]
    resultado = acuerdo(propuestas, revision, _leer(opciones.mapa))
    print(f"Acuerdo {resultado['acuerdo_pct']:.1f} % sobre {resultado['n']}; kappa {resultado['kappa']:.3f}; "
          f"{len(resultado['desacuerdos'])} desacuerdos")
    _escribir(AGENTES / "desacuerdos_enrutador.json",
              [{**d, "final": None, "nota": ""} for d in resultado["desacuerdos"]])
    return 0


def _cmd_fusionar(opciones) -> int:
    propuestas = _leer(opciones.proponente)["casos"] + _leer(opciones.adversario)["casos"]
    revision = _leer(opciones.revisor)["revisiones"]
    adjudicacion = {d["id"]: {"final": d["final"], "nota": d["nota"]} for d in _leer(opciones.desacuerdos)}
    casos = fusionar(propuestas, revision, _leer(opciones.mapa), adjudicacion)
    _escribir(CASOS_PRUEBA, casos)
    print(f"{len(casos)} casos en {CASOS_PRUEBA}")
    return 0


def main(argumentos=None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    sub = analizador.add_subparsers(dest="comando", required=True)
    sub.add_parser("desarrollo").set_defaults(
        ejecutar=lambda o: exportar_desarrollo(AGENTES / "ciego_desarrollo.json") or 0)
    ciego = sub.add_parser("ciego")
    ciego.add_argument("proponente")
    ciego.add_argument("adversario")
    ciego.set_defaults(ejecutar=lambda o: preparar_ciego(
        _leer(o.proponente)["casos"] + _leer(o.adversario)["casos"],
        AGENTES / "ciego_enrutador.json", AGENTES / "mapa_enrutador.json") and 0)
    for nombre, ejecutar in (("acuerdo", _cmd_acuerdo), ("fusionar", _cmd_fusionar)):
        analiza = sub.add_parser(nombre)
        analiza.add_argument("--proponente", default=AGENTES / "proponente_enrutador.json")
        analiza.add_argument("--adversario", default=AGENTES / "adversario_enrutador.json")
        analiza.add_argument("--revisor", default=AGENTES / "revisor_enrutador.json")
        analiza.add_argument("--mapa", default=AGENTES / "mapa_enrutador.json")
        if nombre == "fusionar":
            analiza.add_argument("--desacuerdos", default=AGENTES / "desacuerdos_enrutador.json")
        analiza.set_defaults(ejecutar=ejecutar)
    ejecutar = sub.add_parser("correr")
    ejecutar.add_argument("conjunto", choices=("desarrollo", "prueba"))
    ejecutar.add_argument("--confirmar-envio", action="store_true")
    ejecutar.add_argument("--variantes", action="store_true",
                          help="orden de opciones, redacciones y repetición en la misma solicitud")
    ejecutar.set_defaults(ejecutar=_cmd_correr)
    rej = sub.add_parser("rejilla")
    rej.add_argument("conjunto", choices=("desarrollo", "prueba"), nargs="?", default="desarrollo")
    comp = sub.add_parser("comparar")
    comp.add_argument("conjunto", choices=("desarrollo", "prueba"))
    comp.add_argument("--umbrales", help="noul_si,noul_no,choice_min")
    comp.add_argument("--p95-resto-ms", type=float)

    def _rejilla(o):
        filas = rejilla(_ultima_corrida(o.conjunto), _con_etiqueta(_casos_conjunto(o.conjunto)))
        for fila in filas:
            print(json.dumps(fila))
        print("Elegidos:", elegir_umbrales(filas).model_dump())
        return 0

    def _comparar(o):
        resumen = comparar(_con_etiqueta(_casos_conjunto(o.conjunto)), _ultima_corrida(o.conjunto),
                           _umbrales(o.umbrales))
        print(json.dumps({"resumen": resumen, "veredicto": veredicto(resumen, o.p95_resto_ms)},
                         ensure_ascii=False, indent=2))
        return 0

    rej.set_defaults(ejecutar=_rejilla)
    comp.set_defaults(ejecutar=_comparar)
    opciones = analizador.parse_args(argumentos)
    return opciones.ejecutar(opciones)


if __name__ == "__main__":
    raise SystemExit(main())
