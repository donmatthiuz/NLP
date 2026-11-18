"""Hit@5, MRR@5, abstención y latencia por variante sobre un banco de casos.

python -m licigt.recuperacion.evaluar [casos.json] [--salida resultados.json] [--puntajes]

--puntajes imprime el puntaje del primer resultado de cada caso (respondible o no) y el barrido de umbrales.
Con `make evaluar`, que no pasa argumentos, se piden con LICIGT_EVALUAR_PUNTAJES=1, LICIGT_EVALUAR_SALIDA y
LICIGT_EVALUAR_CASOS.
"""

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from .busqueda import K, UMBRAL, Contexto, _sesion, buscar
from .indice import REVISION, conectar, dispositivo, dtype_modelo

CASOS = Path(__file__).with_name("casos_desarrollo.json")


def relevante(fragmento, relevantes):
    """Relevante si coincide el tipo de documento y alguna página del rango del fragmento."""
    paginas = set(range(fragmento["pagina_inicio"], fragmento["pagina_fin"] + 1))
    return any(r["tipo_documento"] == fragmento["tipo_documento"] and paginas & set(r["paginas"])
               for r in relevantes)


def barrido(puntos):
    """puntos: [(puntaje del primer resultado, respondible)]. Devuelve [(umbral, aciertos)] para cada puntaje
    observado y 0: suficiente = puntaje >= umbral; acierta si suficiente coincide con respondible."""
    umbrales = sorted({0.0, *(p for p, _ in puntos)})
    return [(u, sum((p >= u) == resp for p, resp in puntos)) for u in umbrales]


def leer_como(conn, ctx, sql, params=()):
    """Lectura con la sesión de la empresa (RLS): la conexión de la aplicación no ve filas sin ella."""
    with conn.transaction():
        _sesion(conn, ctx)
        return conn.execute(sql, params).fetchall()


def evaluar(casos, ctx, conn):
    eventos = dict(leer_como(conn, ctx, "SELECT DISTINCT numero_evento, evento_id FROM documentos "
                                        "WHERE tenant_id = %s", (ctx.tenant_id,)))
    resumen, detalle = {}, []
    for variante in ("base", "mejorada"):
        hits, rr, lat, abst_ok, abst_mal = [], [], [], 0, 0
        for caso in casos:
            t = time.perf_counter()
            r = buscar(ctx, eventos[caso["evento"]], caso["pregunta"], variante, conn=conn)
            lat.append(time.perf_counter() - t)
            top = [f for f in r["fragmentos"] if "incluido_por" not in f][:K]
            if not caso["relevantes"]:
                abst_ok += not r["suficiente"]
            else:
                rango = next((i for i, f in enumerate(top, 1) if relevante(f, caso["relevantes"])), None)
                hits.append(rango is not None)
                rr.append(1 / rango if rango else 0.0)
                abst_mal += not r["suficiente"]
            detalle.append({"id": caso["id"], "variante": variante, "suficiente": r["suficiente"],
                            "respondible": bool(caso["relevantes"]), "latencia_s": round(lat[-1], 3),
                            "score_top": r["fragmentos"][0]["score"] if r["fragmentos"] else None,
                            "hit": None if not caso["relevantes"] else rango is not None,
                            "top": [(f["tipo_documento"], f["pagina_inicio"], round(f["score"], 3)) for f in top],
                            "alertas": [a["tipo"] for a in r["alertas"]]})
        resumen[variante] = {
            "hit@5": round(statistics.mean(hits), 3), "mrr@5": round(statistics.mean(rr), 3),
            "abstencion_correcta": f"{abst_ok}/{sum(not c['relevantes'] for c in casos)}",
            "abstencion_indebida": f"{abst_mal}/{len(hits)}",
            "latencia_p50_s": round(statistics.median(lat), 3), "latencia_p95_s": round(statistics.quantiles(lat, n=20)[18], 3), "umbral": UMBRAL[variante]}
    return resumen, detalle


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("casos", nargs="?", default=os.environ.get("LICIGT_EVALUAR_CASOS", CASOS))
    p.add_argument("--tenant-id", default="empresa_demo")  # shortcut: solo desarrollo
    p.add_argument("--salida", default=os.environ.get("LICIGT_EVALUAR_SALIDA"))
    p.add_argument("--puntajes", action="store_true", default=bool(os.environ.get("LICIGT_EVALUAR_PUNTAJES")))
    a = p.parse_args()
    casos = json.loads(Path(a.casos).read_text(encoding="utf-8"))["casos"]
    conn = conectar()
    uno = leer_como(conn, Contexto(a.tenant_id), "SELECT evento_id FROM documentos LIMIT 1")[0][0]
    for v in ("base", "mejorada"):  # carga modelos antes de medir latencia
        buscar(Contexto(a.tenant_id), uno, "calentamiento", v, conn=conn)
    resumen, detalle = evaluar(casos, Contexto(a.tenant_id), conn)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if a.puntajes:
        for v in ("base", "mejorada"):
            filas = [d for d in detalle if d["variante"] == v]
            print(f"\n{v}: puntaje del primer resultado")
            for d in sorted(filas, key=lambda d: d["score_top"] or 0):
                print(f"  {d['score_top'] or 0:8.4f}  {'respondible' if d['respondible'] else 'SIN RESPUESTA'}"
                      f"  suficiente={d['suficiente']}  {d['id']}")
            print(f"{v}: barrido de umbrales (aciertos de suficiencia sobre {len(filas)})")
            for u, n in barrido([(d["score_top"] or 0, d["respondible"]) for d in filas]):
                print(f"  {u:8.4f}  {n}")
    if a.salida:
        Path(a.salida).write_text(json.dumps(
            {"modelos": REVISION, "dispositivo": dispositivo(), "dtype": dtype_modelo(dispositivo()), "casos": str(a.casos),
             "resumen": resumen, "detalle": detalle}, ensure_ascii=False, indent=1), encoding="utf-8")
