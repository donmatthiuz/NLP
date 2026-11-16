"""Importa el paquete de ingesta a PostgreSQL y calcula embeddings de ambas variantes."""

import hashlib
import json
import os
import zipfile
from functools import lru_cache
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

MODELO_BASE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_MEJORADA = "BAAI/bge-m3"
MODELO_RERANKER = "BAAI/bge-reranker-v2-m3"
# Revisiones fijas en Hugging Face para que los resultados sean reproducibles.
REVISION = {
    MODELO_BASE: "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    MODELO_MEJORADA: "5617a9f61b028005a4858fdac845db406aefb181",
    MODELO_RERANKER: "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
}
VENTANA, SOLAPE = 120, 20  # tokens de contenido de la línea base (anteproyecto §10)
SCHEMA = Path(__file__).with_name("schema.sql")


def conectar():
    # autocommit: cada `with conn.transaction()` es una transacción real (y SET LOCAL vive solo en ella).
    url = os.environ.get("LICIGT_DB_URL")
    if not url:  # sin valor por defecto: la contraseña vive en keys/ y `make` arma la URL
        raise RuntimeError("Define LICIGT_DB_URL (o usa `make importar` / `make test-recuperacion`)")
    conn = psycopg.connect(url, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


@lru_cache(maxsize=None)
def modelo(nombre):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(nombre, revision=REVISION[nombre])


def leer_paquete(zip_path):
    """Lee el ZIP sin extraerlo y valida el hash de chunks.jsonl contra el inventario."""
    with zipfile.ZipFile(zip_path) as z:
        inventario = json.loads(z.read("inventario.json"))
        raw = z.read("chunks.jsonl")
        if hashlib.sha256(raw).hexdigest() != inventario["sha256_chunks_jsonl"]:
            raise ValueError("chunks.jsonl no coincide con el SHA-256 del inventario")
        chunks = [json.loads(line) for line in raw.splitlines()]
        manifiestos = {d["doc_id"]: json.loads(z.read(d["manifiesto_zip_path"]))
                       for d in inventario["documents"]}
    return inventario, chunks, manifiestos


def ventanas_base(manifiesto, tokenizer):
    """Ventanas de 120 tokens (solape 20) por página; el texto se recorta del original."""
    meta = manifiesto["metadata"]
    for page in manifiesto["pages"]:
        if page["quality"] != "ok" or not page["text"].strip():
            continue
        text = page["text"]
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
        for n, start in enumerate(range(0, max(len(offsets) - SOLAPE, 1), VENTANA - SOLAPE)):
            win = offsets[start:start + VENTANA]
            texto = text[win[0][0]:win[-1][1]].strip()
            if texto:
                yield {**meta, "chunk_id": f"{manifiesto['doc_id']}:b{page['number']:03d}-{n:03d}",
                       "doc_id": manifiesto["doc_id"], "version_ingesta": manifiesto["version_ingesta"],
                       "pagina_inicio": page["number"], "pagina_fin": page["number"],
                       "seccion": None, "texto": texto}


def importar(zip_path, conn=None, batch=32):
    inventario, chunks, manifiestos = leer_paquete(zip_path)
    conn = conn or conectar()
    with conn.transaction():
        conn.execute(SCHEMA.read_text())
        for d in inventario["documents"]:
            conn.execute(
                """INSERT INTO documentos VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (doc_id) DO UPDATE SET status = EXCLUDED.status,
                     paginas_no_indexadas = EXCLUDED.paginas_no_indexadas, inventario = EXCLUDED.inventario""",
                (d["doc_id"], inventario["tenant_id"], d["evento_id"], d["numero_evento"], d["tipo_documento"],
                 d["version_ingesta"], d["identificador_version_oficial"], d["status"],
                 d["paginas_no_indexadas"], Jsonb(d)))
        # Reimportar reemplaza los fragmentos de los documentos del paquete.
        conn.execute("DELETE FROM fragmentos WHERE doc_id = ANY(%s)", (list(manifiestos),))

        base = [c for m in manifiestos.values() for c in ventanas_base(m, modelo(MODELO_BASE).tokenizer)]
        for variante, filas, nombre, columna in (
            ("base", base, MODELO_BASE, "emb_base"),
            ("mejorada", chunks, MODELO_MEJORADA, "emb_mejorada"),
        ):
            embs = modelo(nombre).encode([c["texto"] for c in filas], batch_size=batch,
                                         normalize_embeddings=True, show_progress_bar=True)
            with conn.cursor() as cur:
                cur.executemany(
                    f"""INSERT INTO fragmentos (chunk_id, variante, doc_id, tenant_id, evento_id, numero_evento,
                          tipo_documento, version_ingesta, pagina_inicio, pagina_fin, seccion, texto, codigos,
                          url_origen, meta, {columna})
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [(c["chunk_id"], variante, c["doc_id"], c["tenant_id"], c["evento_id"], c["numero_evento"],
                      c["tipo_documento"], c["version_ingesta"], c["pagina_inicio"], c["pagina_fin"],
                      c.get("seccion"), c["texto"], c.get("codigos_producto_igss") or [], c["url_origen"],
                      Jsonb({k: v for k, v in c.items() if k != "texto"}), e)
                     for c, e in zip(filas, embs)])
    return {"documentos": len(manifiestos), "base": len(base), "mejorada": len(chunks)}
