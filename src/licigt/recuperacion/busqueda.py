"""Búsqueda autorizada: línea base semántica y versión mejorada híbrida con reranking."""

import re
from dataclasses import dataclass
from functools import lru_cache

from .indice import MODELO_BASE, MODELO_MEJORADA, MODELO_RERANKER, REVISION, conectar, modelo

K, CANDIDATOS, RRF_K = 5, 20, 60
PESO_SEMANTICO, PESO_LEXICO = 0.6, 0.4
# shortcut: umbrales iniciales sin calibrar; ajustarlos con el subconjunto de desarrollo (F6).
# Observado: base da ~0.38 a preguntas fuera de tema y >=0.6 a relevantes; el reranker da ~0.0 fuera de tema.
UMBRAL = {"base": 0.45, "mejorada": 0.10}
NUMERAL = re.compile(r"\b\d+(?:\.\d+)+\b")
CODIGO = re.compile(r"\b\d{2,6}\b")
NUMERAL_MODIFICADO = re.compile(r"(?:sub)?numeral\s+(\d+(?:\.\d+)*)", re.I)

COLUMNAS = """chunk_id, doc_id, tipo_documento, version_ingesta, pagina_inicio, pagina_fin,
              seccion, texto, url_origen, meta->>'identificador_version_oficial'"""
CAMPOS = ("chunk_id", "doc_id", "tipo_documento", "version_ingesta", "pagina_inicio", "pagina_fin",
          "seccion", "texto", "url_origen", "identificador_version_oficial")


@dataclass(frozen=True)
class Contexto:
    """Contexto de acceso ya autenticado; lo construye el rol 4, nunca el usuario."""
    tenant_id: str
    usuario: str = "dev"


@lru_cache(maxsize=None)
def reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(MODELO_RERANKER, revision=REVISION[MODELO_RERANKER])


def _sesion(conn, ctx):
    """Activa RLS para la transacción en curso: rol sin privilegios y empresa del contexto."""
    conn.execute("SET LOCAL ROLE licigt_app")
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (ctx.tenant_id,))
    conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")


def _filas(cur):
    return [dict(zip(CAMPOS, row[:len(CAMPOS)]), _score=row[len(CAMPOS)]) for row in cur.fetchall()]


def _semantica(conn, ctx, evento_id, pregunta, variante, limite, doc_id=None):
    nombre, columna = (MODELO_BASE, "emb_base") if variante == "base" else (MODELO_MEJORADA, "emb_mejorada")
    vec = modelo(nombre).encode(pregunta, normalize_embeddings=True)
    cur = conn.execute(
        f"""SELECT {COLUMNAS}, 1 - ({columna} <=> %(v)s) FROM fragmentos
            WHERE tenant_id = %(t)s AND evento_id = %(e)s AND variante = %(var)s
              AND (%(d)s::text IS NULL OR doc_id = %(d)s)
            ORDER BY {columna} <=> %(v)s LIMIT %(n)s""",
        {"v": vec, "t": ctx.tenant_id, "e": evento_id, "var": variante, "d": doc_id, "n": limite})
    return _filas(cur)


def _lexica(conn, ctx, evento_id, pregunta, limite, doc_id=None):
    """tsvector en español con OR entre términos, más coincidencia exacta de códigos y numerales."""
    cur = conn.execute(
        f"""WITH q AS (SELECT replace(plainto_tsquery('spanish', %(q)s)::text, '&', '|') AS s)
            SELECT {COLUMNAS},
                   ts_rank_cd(tsv, to_tsquery('spanish', q.s))
                   + CASE WHEN codigos && %(cod)s THEN 1 ELSE 0 END
                   + CASE WHEN split_part(trim(seccion), ' ', 1) = ANY(%(num)s) THEN 1 ELSE 0 END
            FROM fragmentos, q
            WHERE tenant_id = %(t)s AND evento_id = %(e)s AND variante = 'mejorada'
              AND (%(d)s::text IS NULL OR doc_id = %(d)s)
              AND (q.s <> '' AND tsv @@ to_tsquery('spanish', q.s)
                   OR codigos && %(cod)s OR split_part(trim(seccion), ' ', 1) = ANY(%(num)s))
            ORDER BY 11 DESC LIMIT %(n)s""",
        {"q": pregunta, "cod": CODIGO.findall(pregunta), "num": NUMERAL.findall(pregunta),
         "t": ctx.tenant_id, "e": evento_id, "d": doc_id, "n": limite})
    return _filas(cur)


def rrf(listas_ponderadas, k=RRF_K):
    """Reciprocal Rank Fusion ponderada: [(peso, [fila, ...]), ...] -> filas ordenadas."""
    puntaje, filas = {}, {}
    for peso, lista in listas_ponderadas:
        for rango, fila in enumerate(lista, 1):
            puntaje[fila["chunk_id"]] = puntaje.get(fila["chunk_id"], 0) + peso / (k + rango)
            filas.setdefault(fila["chunk_id"], fila)
    return [dict(filas[c], rrf=puntaje[c]) for c in sorted(puntaje, key=puntaje.get, reverse=True)]


def _redundante(a, b):
    """Mismo documento, páginas solapadas y texto casi igual; otra versión nunca es redundante."""
    if a["doc_id"] != b["doc_id"] or a["pagina_fin"] < b["pagina_inicio"] or b["pagina_fin"] < a["pagina_inicio"]:
        return False
    x, y = set(a["texto"].lower().split()), set(b["texto"].lower().split())
    return len(x & y) / max(1, min(len(x), len(y))) > 0.8


def _bajo_numeral(seccion, numeral):
    """'2.2.6 ...' está bajo '2.2'; '2.21 ...' no."""
    tok = (seccion.split() or [""])[0].rstrip(".")
    return tok == numeral or tok.startswith(numeral + ".")


def _alertas(conn, ctx, evento_id, pregunta, resultados):
    """Cobertura incompleta y posibles conflictos con modificaciones o aclaraciones del evento."""
    docs = conn.execute(
        """SELECT doc_id, tipo_documento, status, paginas_no_indexadas, identificador_version_oficial
           FROM documentos WHERE tenant_id = %s AND evento_id = %s""", (ctx.tenant_id, evento_id)).fetchall()
    alertas, extra = [], []
    for doc_id, tipo, status, no_idx, oficial in docs:
        if status != "completo" or no_idx:
            alertas.append({"tipo": "cobertura_incompleta", "doc_id": doc_id, "paginas_no_indexadas": no_idx,
                            "status": status})
        if tipo not in ("modificacion", "aclaracion"):
            continue
        textos = conn.execute("SELECT texto FROM fragmentos WHERE doc_id = %s AND variante = 'mejorada'",
                              (doc_id,)).fetchall()
        modificados = {n for (t,) in textos for n in NUMERAL_MODIFICADO.findall(t)}
        afectados = [r["chunk_id"] for r in resultados if r["doc_id"] != doc_id and r["seccion"]
                     and any(_bajo_numeral(r["seccion"], n) for n in modificados)]
        if afectados or any(r["doc_id"] == doc_id for r in resultados):
            alertas.append({"tipo": "posible_conflicto", "doc_id": doc_id, "documento": oficial,
                            "numerales_modificados": sorted(modificados), "chunk_ids_afectados": afectados})
            if afectados and not any(r["doc_id"] == doc_id for r in resultados):
                # Conservar la cláusula base y el documento que la modifica.
                extra += _semantica(conn, ctx, evento_id, pregunta, "mejorada", 1, doc_id=doc_id)
        elif tipo == "modificacion":
            alertas.append({"tipo": "evento_con_modificaciones", "doc_id": doc_id, "documento": oficial})
    return alertas, extra


def buscar(ctx, evento_id, pregunta, variante="mejorada", k=K, conn=None):
    """Devuelve evidencia autorizada del evento con puntajes, alertas y suficiencia."""
    if variante not in UMBRAL:
        raise ValueError(f"variante desconocida: {variante}")
    conn = conn or conectar()
    with conn.transaction():
        _sesion(conn, ctx)
        if variante == "base":
            resultados = _semantica(conn, ctx, evento_id, pregunta, "base", k)
            for r in resultados:
                r["score"] = r["semantico"] = r.pop("_score")
        else:
            sem = _semantica(conn, ctx, evento_id, pregunta, "mejorada", CANDIDATOS)
            lex = _lexica(conn, ctx, evento_id, pregunta, CANDIDATOS)
            sem_s = {r["chunk_id"]: r["_score"] for r in sem}
            lex_s = {r["chunk_id"]: r["_score"] for r in lex}
            candidatos = rrf([(PESO_SEMANTICO, sem), (PESO_LEXICO, lex)])[:CANDIDATOS]
            if candidatos:
                scores = reranker().predict([(pregunta, c["texto"]) for c in candidatos])
                for c, s in zip(candidatos, scores):
                    c.update(score=float(s), reranker=float(s), semantico=sem_s.get(c["chunk_id"]),
                             lexico=lex_s.get(c["chunk_id"]))
                    c.pop("_score")
            resultados = []
            for c in sorted(candidatos, key=lambda c: c["score"], reverse=True):
                if len(resultados) < k and not any(_redundante(c, r) for r in resultados):
                    resultados.append(c)
        alertas, extra = _alertas(conn, ctx, evento_id, pregunta, resultados)
        for e in extra:
            e["score"] = e["semantico"] = e.pop("_score")
            e["incluido_por"] = "posible_conflicto"
        resultados += extra
    suficiente = bool(resultados) and resultados[0]["score"] >= UMBRAL[variante]
    return {"evento_id": evento_id, "variante": variante, "suficiente": suficiente,
            "fragmentos": resultados, "alertas": alertas}


def comparar_versiones(ctx, evento_id, pregunta, k=2, conn=None):
    """Mejores fragmentos de cada documento del evento, para contrastar bases y modificaciones."""
    conn = conn or conectar()
    with conn.transaction():
        _sesion(conn, ctx)
        docs = conn.execute("""SELECT doc_id, tipo_documento, identificador_version_oficial FROM documentos
                               WHERE tenant_id = %s AND evento_id = %s ORDER BY tipo_documento""",
                            (ctx.tenant_id, evento_id)).fetchall()
        return {"evento_id": evento_id, "documentos": [
            {"doc_id": d, "tipo_documento": t, "identificador_version_oficial": o,
             "fragmentos": [dict(f, score=f.pop("_score"))
                            for f in _semantica(conn, ctx, evento_id, pregunta, "mejorada", k, doc_id=d)]}
            for d, t, o in docs]}
