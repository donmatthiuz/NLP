"""Migra los chunk_id viejos a los del paquete regenerado (extracción de tablas, R3)."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

ID = re.compile(r"[0-9a-f]{32}:\d{5}")
TOKEN = re.compile(r"\w+")
PIE = re.compile(r"^\s*\d{1,3}(?:\s+Extensi[óo]n:\s*\d+)?\s*$")  # número de página o pie suelto
UMBRAL = 0.9


def _chunks(paquete: Path) -> list[dict]:
    with zipfile.ZipFile(paquete) as z:
        return [json.loads(linea) for linea in z.read("chunks.jsonl").splitlines() if linea.strip()]


def _normal(texto: str) -> str:
    return " ".join(texto.split())


def ids_con_otro_texto(zip_viejo: Path, zip_nuevo: Path) -> list[str]:
    """Ids del paquete viejo que en el nuevo no existen o apuntan a otro texto (normalizado)."""
    nuevos = {c["chunk_id"]: _normal(c["texto"]) for c in _chunks(zip_nuevo)}
    return sorted(c["chunk_id"] for c in _chunks(zip_viejo)
                  if nuevos.get(c["chunk_id"]) != _normal(c["texto"]))


def calcular_equivalencias(zip_viejo: Path, zip_nuevo: Path, ids: list[str]) -> dict[str, dict]:
    """Para cada id viejo, el nuevo cuyo texto es el mismo ("identico") o contiene todo el texto
    en las mismas palabras ("contenido"); sin un único candidato queda en "revision"."""
    viejos = {c["chunk_id"]: c for c in _chunks(zip_viejo)}
    nuevos = _chunks(zip_nuevo)
    tabla = {}
    for id_viejo in sorted(set(ids)):
        antiguo = viejos.get(id_viejo)
        if antiguo is None:
            tabla[id_viejo] = {"nuevo": None, "estado": "revision", "candidatos": [], "motivo": "id ausente del paquete viejo"}
            continue
        del_doc = [c for c in nuevos if c["doc_id"] == antiguo["doc_id"]]
        texto = _normal(antiguo["texto"])
        fin = antiguo.get("pagina_fin", antiguo["pagina_inicio"])
        iguales = [c["chunk_id"] for c in del_doc
                   if _normal(c["texto"]) == texto and antiguo["pagina_inicio"] <= c["pagina_inicio"] <= fin]
        if len(iguales) == 1:
            tabla[id_viejo] = {"nuevo": iguales[0], "estado": "identico", "candidatos": iguales}
            continue
        sin_pies = "\n".join(l for l in antiguo["texto"].splitlines() if not PIE.match(l))
        palabras = Counter(TOKEN.findall(sin_pies))
        total = sum(palabras.values())
        candidatos = []
        for c in del_doc:
            if not antiguo["pagina_inicio"] <= c["pagina_inicio"] <= antiguo.get("pagina_fin", antiguo["pagina_inicio"]):
                continue
            comun = sum((palabras & Counter(TOKEN.findall(c["texto"]))).values())
            if total and comun / total >= UMBRAL:
                candidatos.append(c["chunk_id"])
        estado = "contenido" if len(candidatos) == 1 else "revision"
        tabla[id_viejo] = {"nuevo": candidatos[0] if estado == "contenido" else None,
                           "estado": estado, "candidatos": candidatos}
    return tabla


def migrar(archivos: list[Path], tabla: dict[str, dict], *, aplicar: bool = False) -> dict:
    """Reemplaza ids viejos por nuevos en una sola pasada; los marcados para revisión no se tocan."""
    reemplazos, revision, detalle = 0, [], []
    for archivo in map(Path, archivos):
        texto = archivo.read_text(encoding="utf-8")
        cambios = []

        def sustituir(m: re.Match) -> str:
            entrada = tabla.get(m.group(0))
            if entrada is None:
                return m.group(0)
            if not entrada.get("nuevo"):
                if m.group(0) not in revision:
                    revision.append(m.group(0))
                return m.group(0)
            cambios.append((m.group(0), entrada["nuevo"]))
            return entrada["nuevo"]

        nuevo_texto = ID.sub(sustituir, texto)
        if cambios:
            detalle.append({"archivo": archivo.as_posix(), "cambios": cambios})
            reemplazos += len(cambios)
            if aplicar:
                archivo.write_text(nuevo_texto, encoding="utf-8")
    return {"aplicado": aplicar, "reemplazos": reemplazos, "revision": revision, "detalle": detalle}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="orden", required=True)
    calcular = sub.add_parser("equivalencias", help="genera la tabla desde el paquete viejo y el nuevo")
    calcular.add_argument("--viejo", type=Path, required=True)
    calcular.add_argument("--nuevo", type=Path, required=True)
    calcular.add_argument("--salida", type=Path, required=True)
    calcular.add_argument("--todos", action="store_true",
                          help="incluye todos los ids viejos cuyo texto cambió, no solo los citados en los archivos")
    calcular.add_argument("archivos", nargs="*", type=Path, help="archivos donde buscar ids citados")
    aplicar = sub.add_parser("migrar", help="reemplaza ids; sin --aplicar solo muestra la vista previa")
    aplicar.add_argument("--tabla", type=Path, required=True)
    aplicar.add_argument("--aplicar", action="store_true")
    aplicar.add_argument("archivos", nargs="+", type=Path)
    args = parser.parse_args()
    if args.orden == "equivalencias":
        ids = [i for a in args.archivos for i in ID.findall(a.read_text(encoding="utf-8"))]
        if args.todos:
            ids += ids_con_otro_texto(args.viejo, args.nuevo)
        elif not args.archivos:
            parser.error("indica archivos o --todos")
        tabla = calcular_equivalencias(args.viejo, args.nuevo, ids)
        args.salida.write_text(json.dumps({"version": 1, "equivalencias": tabla}, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(json.dumps({"ids": len(tabla), "revision": [i for i, e in tabla.items() if e["estado"] == "revision"]},
                         ensure_ascii=False, indent=2))
        return 0
    tabla = json.loads(args.tabla.read_text(encoding="utf-8"))["equivalencias"]
    print(json.dumps(migrar(args.archivos, tabla, aplicar=args.aplicar), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
