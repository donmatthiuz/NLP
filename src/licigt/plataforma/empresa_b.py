"""make empresa-b: arma el paquete de la empresa ficticia empresa_b con un solo evento de empresa_demo.

doc_id y chunk_id son clave primaria en el esquema del rol 2, así que no pueden repetirse entre empresas:
el doc_id de empresa_b es un derivado fijo del original (sha256 de "empresa_b:" + doc_id original, 32 hex)
y cada chunk_id conserva su sufijo (`<doc_id nuevo>:00001`). El evento_id y el numero_evento no cambian
(no son clave única). El PDF original y su sha256 son los mismos; solo cambia el nombre en el paquete."""

import hashlib
import json
import sys
import zipfile

from .rutas import RAIZ

EMPRESA = "empresa_b"
EVENTO = "363-IGSS-2026"
ORIGEN = RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip"
DESTINO = RAIZ / "data" / "plataforma" / "empresa_b.zip"


def doc_id_de_empresa(doc_id: str) -> str:
    return hashlib.sha256(f"{EMPRESA}:{doc_id}".encode()).hexdigest()[:32]


def _con_empresa(objeto):
    """Cambia todo tenant_id anidado (el manifiesto lo repite en cada chunk)."""
    if isinstance(objeto, dict):
        return {k: EMPRESA if k == "tenant_id" else _con_empresa(v) for k, v in objeto.items()}
    if isinstance(objeto, list):
        return [_con_empresa(v) for v in objeto]
    return objeto


def _json(objeto) -> bytes:
    return json.dumps(objeto, ensure_ascii=False, indent=2).encode()


def armar(origen=ORIGEN, destino=DESTINO, evento=EVENTO) -> dict:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(origen) as z:
        inventario = json.loads(z.read("inventario.json"))
        propios = [d for d in inventario["documents"] if d["numero_evento"] == evento]
        if not propios:
            raise SystemExit(f"El paquete no trae el evento {evento}")
        nuevos = {d["doc_id"]: doc_id_de_empresa(d["doc_id"]) for d in propios}
        chunks = []
        for linea in z.read("chunks.jsonl").splitlines():
            c = json.loads(linea)
            if c["doc_id"] in nuevos:
                nuevo = nuevos[c["doc_id"]]
                c.update(tenant_id=EMPRESA, doc_id=nuevo, chunk_id=c["chunk_id"].replace(c["doc_id"], nuevo, 1))
                chunks.append(c)
        crudo = ("\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n").encode()
        documentos = []
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as salida:
            for d in propios:
                viejo, nuevo = d["doc_id"], nuevos[d["doc_id"]]
                manifiesto = json.loads(z.read(d["manifiesto_zip_path"]))
                texto = json.dumps(manifiesto, ensure_ascii=False).replace(viejo, nuevo)
                manifiesto = _con_empresa(json.loads(texto))
                original = f"originales/{nuevo}.pdf"
                salida.writestr(original, z.read(d["original_zip_path"]))
                salida.writestr(f"manifiestos/{nuevo}.json", _json(manifiesto))
                salida.writestr(f"procedencia/{nuevo}.json",
                                z.read(d["procedencia_zip_path"]).decode().replace(viejo, nuevo))
                documentos.append({**d, "doc_id": nuevo, "original_zip_path": original,
                                   "manifiesto_zip_path": f"manifiestos/{nuevo}.json",
                                   "procedencia_zip_path": f"procedencia/{nuevo}.json"})
            salida.writestr("chunks.jsonl", crudo)
            salida.writestr("inventario.json", _json({
                **inventario, "tenant_id": EMPRESA, "documents": documentos,
                "chunks_indexables": sum(d["chunks_indexables"] for d in documentos),
                "chunks_excluidos": sum(d["chunks_excluidos"] for d in documentos),
                "sha256_chunks_jsonl": hashlib.sha256(crudo).hexdigest()}))
    return {"tenant_id": EMPRESA, "evento": evento, "documentos": len(documentos), "chunks": len(chunks)}


if __name__ == "__main__":
    print(armar(), file=sys.stdout)
