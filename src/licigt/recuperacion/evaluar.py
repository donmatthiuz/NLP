"""Hit@5, MRR@5, abstención y latencia por variante sobre un banco de casos.

python -m licigt.recuperacion.evaluar [casos.json] [--salida resultados.json]
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from .busqueda import K, UMBRAL, Contexto, buscar
from .indice import REVISION, conectar

CASOS = Path(__file__).with_name("casos_desarrollo.json")


def relevante(fragmento, relevantes):
    """Relevante si coincide el tipo de documento y alguna página del rango del fragmento."""
    paginas = set(range(fragmento["pagina_inicio"], fragmento["pagina_fin"] + 1))
    return any(r["tipo_documento"] == fragmento["tipo_documento"] and paginas & set(r["paginas"])
               for r in relevantes)


def evaluar(casos, ctx, conn):
    eventos = dict(conn.execute("SELECT DISTINCT numero_evento, evento_id FROM documentos WHERE tenant_id = %s",
                                (ctx.tenant_id,)).fetchall())
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
                            "top": [(f["tipo_documento"], f["pagina_inicio"], round(f["score"], 3)) for f in top],
                            "alertas": [a["tipo"] for a in r["alertas"]]})
        resumen[variante] = {
            "hit@5": round(statistics.mean(hits), 3), "mrr@5": round(statistics.mean(rr), 3),
            "abstencion_correcta": f"{abst_ok}/{sum(not c['relevantes'] for c in casos)}",
            "abstencion_indebida": f"{abst_mal}/{len(hits)}",
            "latencia_p95_s": round(statistics.quantiles(lat, n=20)[18], 3), "umbral": UMBRAL[variante]}
    return resumen, detalle


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("casos", nargs="?", default=CASOS)
    p.add_argument("--tenant-id", default="empresa_demo")  # shortcut: solo desarrollo
    p.add_argument("--salida")
    a = p.parse_args()
    casos = json.loads(Path(a.casos).read_text(encoding="utf-8"))["casos"]
    conn = conectar()
    uno = conn.execute("SELECT evento_id FROM documentos LIMIT 1").fetchone()[0]
    for v in ("base", "mejorada"):  # carga modelos antes de medir latencia
        buscar(Contexto(a.tenant_id), uno, "calentamiento", v, conn=conn)
    resumen, detalle = evaluar(casos, Contexto(a.tenant_id), conn)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if a.salida:
        Path(a.salida).write_text(json.dumps(
            {"modelos": REVISION, "casos": str(a.casos),
             "resumen": resumen, "detalle": detalle}, ensure_ascii=False, indent=1), encoding="utf-8")
