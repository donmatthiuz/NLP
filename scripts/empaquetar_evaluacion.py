"""Empaqueta la corrida oficial y sus bancos sin volver a medir ni incluir auditorías."""

import hashlib
import json
from pathlib import Path
import zipfile


RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = {
    "README.md": "entregables/evaluacion/README.md",
    "bancos/comun.json": "src/licigt/plataforma/casos_comun.json",
    "bancos/rol3.json": "src/licigt/consulta/casos_banco.json",
    "bancos/desarrollo.json": "src/licigt/recuperacion/casos_desarrollo.json",
    "bancos/calibracion.json": "src/licigt/recuperacion/casos_calibracion.json",
    "resultados/reporte.json": "data/plataforma/reporte/20261119T061552Z.json",
    "resultados/reporte.md": "data/plataforma/reporte/20261119T061552Z.md",
    "resultados/rol3.json": "data/plataforma/reporte/detalle/20261119T061618Z.json",
    "resultados/comun.json": "data/plataforma/reporte/detalle/20261119T061751Z.json",
}


def main():
    contenidos = {destino: (RAIZ / origen).read_bytes() for destino, origen in ARCHIVOS.items()}
    reporte = json.loads(contenidos["resultados/reporte.json"])
    for banco, cantidad in (("comun", 20), ("rol3", 23)):
        casos = json.loads(contenidos[f"bancos/{banco}.json"])["casos"]
        salida = json.loads(contenidos[f"resultados/{banco}.json"])
        ids = [caso["id"] for caso in casos]
        if len(ids) != cantidad or len(set(ids)) != cantidad:
            raise ValueError(f"Cantidad o ids inesperados: {banco}")
        if set(ids) != {caso["id"] for caso in salida["resultados"]}:
            raise ValueError(f"El banco no coincide con sus resultados: {banco}")
        if salida["commit"] != reporte["commit"]:
            raise ValueError(f"El detalle no corresponde al commit oficial: {banco}")
    manifiesto = {
        "corrida": "20261119T061552Z",
        "commit_medicion": reporte["commit"],
        "arbol_sucio_en_medicion": reporte["commit_sucio"],
        "nota": "Copias de resultados existentes, no una nueva evaluación. Ver README y limitaciones.",
        "archivos": [
            {"archivo": destino, "origen": ARCHIVOS[destino], "sha256": hashlib.sha256(datos).hexdigest()}
            for destino, datos in contenidos.items()
        ],
    }
    contenidos["manifiesto.json"] = (json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n").encode()
    destino = RAIZ / "entregables/evaluacion/Evaluacion_LiciGT.zip"
    temporal = destino.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporal, "w", compression=zipfile.ZIP_DEFLATED) as paquete:
            for nombre, datos in contenidos.items():
                info = zipfile.ZipInfo(nombre, date_time=(2026, 11, 19, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                paquete.writestr(info, datos)
        with zipfile.ZipFile(temporal) as paquete:
            if paquete.testzip() is not None:
                raise ValueError("El paquete no pasó la verificación CRC")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)
    print(f"ok\t{destino.relative_to(RAIZ)}\t20 casos comunes y 23 del rol 3")


if __name__ == "__main__":
    main()
