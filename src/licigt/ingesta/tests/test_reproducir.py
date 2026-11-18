import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from licigt.ingesta import prepare_corpus, reproducir
from licigt.ingesta.automatic import PortalEvent, event_id_for
from licigt.ingesta.handoff import export
from licigt.ingesta.pdf import Page
from licigt.ingesta.pipeline import IngestionService, SourceMetadata

RAIZ = Path(__file__).resolve().parents[4]
ZIP_ACTUAL = Path(os.environ.get("LICIGT_ZIP_CORPUS") or RAIZ / "entregables" / "recuperacion" / "empresa_demo.zip")
TENANT = "empresa_demo"
URL_BASES = "https://www.igssgt.org/wp-content/uploads/2026/11/bases-399.pdf"
URL_MOD = "https://www.igssgt.org/wp-content/uploads/2026/11/modificacion-399.pdf"
RUTA_ABSOLUTA = re.compile(r"(?:^|[\"' ])(?:/(?:home|tmp|var|Users|mnt)/|[A-Za-z]:[\\/]|file://)")

PAGINAS = {
    b"%PDF-1.4\nbases": [
        Page(1, "DOCUMENTOS DE LICITACIÓN 399-IGSS-2026\nCÓDIGO IGSS 432\nBases de licitación", "text", "ok"),
        Page(2, "1. REQUISITOS\nLa oferta debe incluir constancia.", "text", "ok"),
    ],
    b"%PDF-1.4\nmodificacion": [
        Page(1, "MODIFICACIÓN 1 DE 399-IGSS-2026\nSe cambia el plazo.", "text", "ok"),
        Page(2, "", "text", "incompleta", ["OCR no disponible: instala Tesseract y el idioma spa"]),
        Page(3, "Segunda hoja de la modificación.", "text", "ok"),
    ],
}


def _extraer(path, **_):
    return PAGINAS[Path(path).read_bytes()]


def _sidecar(numero, contenido, url, declarado):
    digest = hashlib.sha256(contenido).hexdigest()
    return digest, {
        "numero_evento": numero, "anio": 2026, "modalidad": "Licitación Pública DA",
        "titulo": "Multivitamínico prenatal", "unidad_requirente": "UNIDADES MÉDICAS",
        "codigo_igss": "432", "fecha_publicacion": None,
        "fecha_descarga": "2026-11-14T18:14:00.880506-06:00",
        "pagina_origen": "https://www.igssgt.org/proveedores/", "enlace_en_ficha": declarado is None,
        "tipo_documento_declarado": declarado, "url_origen": url, "sha256": digest,
        "bytes": len(contenido), "fecha_ficha": "2026-11-13",
    }


def _parches():
    return (patch("licigt.ingesta.pipeline.extract_pages", side_effect=_extraer),
            patch("licigt.ingesta.pipeline.extract_hidden_text", return_value={}))


def _zip_de_origen(raiz: Path) -> Path:
    """Arma un paquete con uuid4 y hora real, como el que se entregó antes de fijar los ids."""
    data = raiz / "origen"
    servicio = IngestionService(data)
    for contenido, url, clave, tipo, version, relacion, declarado in (
            (b"%PDF-1.4\nbases", URL_BASES, "bases_integradas", "bases", None, None, None),
            (b"%PDF-1.4\nmodificacion", URL_MOD, "modificacion_1", "modificacion",
             "Modificación Número 1", "bases_integradas", "modificacion")):
        digest, sidecar = _sidecar("399-IGSS-2026", contenido, url, declarado)
        carpeta = data / "descargas_igss" / "399-IGSS-2026"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"{digest}.pdf").write_bytes(contenido)
        (carpeta / f"{digest}.json").write_text(json.dumps({**sidecar, "archivo": f"{digest}.pdf"}))
        evento = event_id_for(TENANT, PortalEvent(
            "399-IGSS-2026", 2026, "Licitación Pública DA", "Multivitamínico prenatal",
            "UNIDADES MÉDICAS", "432", "2026-11-13", url))
        servicio.ingest(carpeta / f"{digest}.pdf", SourceMetadata(
            tenant_id=TENANT, evento_id=evento, numero_evento="399-IGSS-2026", anio=2026,
            modalidad="Licitación Pública DA", document_key=clave, tipo_documento=tipo,
            titulo="Multivitamínico prenatal", url_origen=url, unidad_requirente="UNIDADES MÉDICAS",
            codigos_producto_igss=("432",), fecha_ficha="2026-11-13", fecha_descarga="2026-11-14",
            identificador_version_oficial=version, relacion_documental=relacion))
    salida = raiz / "origen.zip"
    export(data, TENANT, salida)
    return salida


def _leer(zip_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(zip_path) as archivo:
        return {nombre: archivo.read(nombre) for nombre in archivo.namelist()}


class EspecificacionTests(unittest.TestCase):
    def test_se_genera_desde_el_paquete_con_los_campos_del_encargo(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            zip_path = _zip_de_origen(Path(temporal))
            spec = reproducir.generar_especificacion(zip_path)
        self.assertEqual(spec["tenant_id"], TENANT)
        self.assertEqual([d["document_key"] for d in spec["documentos"]],
                         ["bases_integradas", "modificacion_1"])
        campos = {"numero_evento", "evento_id", "tenant_id", "document_key", "tipo_documento",
                  "version_oficial", "relacion_documental", "url_origen", "sha256", "doc_id",
                  "version_ingesta", "ingested_at", "paginas_ocr", "advertencias_humanas", "procedencia"}
        for documento in spec["documentos"]:
            self.assertEqual(set(documento), campos)
        modificacion = spec["documentos"][1]
        self.assertEqual(modificacion["paginas_ocr"], [2])
        self.assertEqual(modificacion["version_oficial"], "Modificación Número 1")
        self.assertEqual(modificacion["relacion_documental"], "bases_integradas")
        self.assertEqual(spec["documentos"][0]["paginas_ocr"], [])
        self.assertIsNone(RUTA_ABSOLUTA.search(json.dumps(spec, ensure_ascii=False)))

    def test_la_especificacion_versionada_describe_los_seis_documentos(self):
        spec = reproducir.cargar_especificacion()
        self.assertEqual(spec["tenant_id"], TENANT)
        self.assertEqual(len(spec["documentos"]), 6)
        self.assertEqual(len({d["doc_id"] for d in spec["documentos"]}), 6)
        self.assertEqual(len({d["numero_evento"] for d in spec["documentos"]}), 5)
        self.assertIsNone(RUTA_ABSOLUTA.search(json.dumps(spec, ensure_ascii=False)))
        self.assertIn("03791a3471c04c0f9cc260814564756e", {d["doc_id"] for d in spec["documentos"]})


class OcrDeLaEspecificacionTests(unittest.TestCase):
    def test_la_especificacion_fija_el_motor_y_la_advertencia_del_anexo(self):
        spec = reproducir.cargar_especificacion()
        self.assertEqual(spec["ocr"], {"motor": "tesseract", "version": "4.1.1", "idioma": "spa"})
        modificacion = next(d for d in spec["documentos"] if d["doc_id"] == "d41480e5b0ce4c16bf18f66225ada2dc")
        self.assertEqual(modificacion["advertencias_humanas"],
                         ["Menciona un anexo de 11 hojas que no está cargado"])

    def test_version_de_tesseract_se_lee_de_version(self):
        salida = subprocess.CompletedProcess([], 0, stdout="tesseract 4.1.1\n leptonica-1.79.0\n", stderr="")
        with patch("licigt.ingesta.reproducir.subprocess.run", return_value=salida):
            self.assertEqual(reproducir.version_tesseract(), "4.1.1")
        with patch("licigt.ingesta.reproducir.subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(reproducir.version_tesseract())

    def test_avisa_si_la_version_instalada_difiere(self):
        a, b = _parches()
        recuperada = Page(2, "Texto recuperado por OCR " + "con palabras suficientes para ser legible y no contarse como ruido " * 3, "ocr", "ok")
        mod = PAGINAS[b"%PDF-1.4\nmodificacion"]
        with tempfile.TemporaryDirectory() as temporal, a, b:
            raiz = Path(temporal)
            zip_origen = _zip_de_origen(raiz)
            spec = reproducir.generar_especificacion(zip_origen)
            spec["ocr"] = {"motor": "tesseract", "version": "4.1.1", "idioma": "spa"}
            originales = reproducir.originales_desde_zip(zip_origen, spec)
            with patch("licigt.ingesta.reextraer.extract_pages", return_value=[mod[0], recuperada, mod[2]]), \
                    patch("licigt.ingesta.reproducir.version_tesseract", return_value="5.3.0"):
                resultado = reproducir.reproducir(spec, originales, raiz / "s.zip", ocr=True)
            with patch("licigt.ingesta.reextraer.extract_pages", return_value=[mod[0], recuperada, mod[2]]), \
                    patch("licigt.ingesta.reproducir.version_tesseract", return_value="4.1.1"):
                igual = reproducir.reproducir(spec, originales, raiz / "t.zip", ocr=True)
        self.assertTrue(any("5.3.0" in aviso and "4.1.1" in aviso for aviso in resultado["avisos"]))
        self.assertFalse(any("versión" in aviso for aviso in igual["avisos"]))


class ReproducirTests(unittest.TestCase):
    def _reproducir_desde(self, raiz, **opciones):
        zip_origen = _zip_de_origen(raiz)
        spec = reproducir.generar_especificacion(zip_origen)
        salida = raiz / "salida" / "nuevo.zip"
        resultado = reproducir.reproducir(
            spec, reproducir.originales_desde_zip(zip_origen, spec), salida, **opciones)
        return zip_origen, spec, salida, resultado

    def test_reconstruye_el_paquete_con_los_mismos_ids(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            zip_origen, spec, salida, _ = self._reproducir_desde(Path(temporal), ocr=False)
            antes, despues = _leer(zip_origen), _leer(salida)
        self.assertEqual(sorted(antes), sorted(despues))
        self.assertEqual(antes["chunks.jsonl"], despues["chunks.jsonl"])
        self.assertEqual({d["doc_id"] for d in spec["documentos"]},
                         {json.loads(l)["doc_id"] for l in despues["chunks.jsonl"].splitlines()})
        for nombre in antes:
            if nombre == "chunks.jsonl" or nombre.startswith("originales/"):
                continue
            esperado, obtenido = json.loads(antes[nombre]), json.loads(despues[nombre])
            esperado.pop("generated_at", None), obtenido.pop("generated_at", None)
            self.assertEqual(esperado, obtenido, nombre)
        for nombre, contenido in despues.items():
            if nombre.endswith((".json", ".jsonl")):
                self.assertIsNone(RUTA_ABSOLUTA.search(contenido.decode("utf-8")), nombre)

    def test_sha256_distinto_falla_sin_escribir(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            raiz = Path(temporal)
            zip_origen = _zip_de_origen(raiz)
            spec = reproducir.generar_especificacion(zip_origen)
            originales = reproducir.originales_desde_zip(zip_origen, spec)
            sha = spec["documentos"][1]["sha256"]
            originales[sha] = originales[sha] + b"alterado"
            salida = raiz / "salida" / "nuevo.zip"
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                reproducir.reproducir(spec, originales, salida, ocr=False)
            self.assertFalse(salida.exists())
            self.assertFalse(salida.parent.exists() and any(salida.parent.iterdir()))

    def test_falta_un_original_falla(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            raiz = Path(temporal)
            spec = reproducir.generar_especificacion(_zip_de_origen(raiz))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                reproducir.reproducir(spec, {}, raiz / "x.zip", ocr=False)

    def test_sin_spa_avisa_y_deja_las_paginas_ilegibles(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            _, _, salida, resultado = self._reproducir_desde(Path(temporal), ocr=False)
            inventario = json.loads(_leer(salida)["inventario.json"])
        self.assertTrue(any("spa" in aviso for aviso in resultado["avisos"]))
        modificacion = inventario["documents"][1]
        self.assertEqual(modificacion["paginas_no_indexadas"], [2])
        self.assertEqual(modificacion["status"], "requiere_revision")

    def test_con_spa_aplica_reextraer_a_los_documentos_con_paginas_ocr(self):
        a, b = _parches()
        recuperada = Page(2, "Texto recuperado por OCR " + "con palabras suficientes para ser legible y no contarse como ruido " * 3, "ocr", "ok")
        with tempfile.TemporaryDirectory() as temporal, a, b:
            raiz = Path(temporal)
            zip_origen = _zip_de_origen(raiz)
            spec = reproducir.generar_especificacion(zip_origen)
            originales = reproducir.originales_desde_zip(zip_origen, spec)
            doc_mod = spec["documentos"][1]["doc_id"]
            with patch("licigt.ingesta.reextraer.extract_pages",
                       return_value=[PAGINAS[b"%PDF-1.4\nmodificacion"][0], recuperada,
                                     PAGINAS[b"%PDF-1.4\nmodificacion"][2]]):
                resultado = reproducir.reproducir(spec, originales, raiz / "s.zip", ocr=True)
            inventario = json.loads(_leer(raiz / "s.zip")["inventario.json"])
        self.assertEqual(resultado["ocr"], {doc_mod: [2]})
        self.assertEqual(inventario["documents"][1]["paginas_no_indexadas"], [])

    def test_tesseract_con_spa_se_detecta_por_list_langs(self):
        salida = subprocess.CompletedProcess([], 0, stdout="List of available languages (2):\neng\nspa\n")
        with patch("licigt.ingesta.reproducir.subprocess.run", return_value=salida):
            self.assertTrue(reproducir.tesseract_con_spa())
        salida = subprocess.CompletedProcess([], 0, stdout="List of available languages (2):\neng\nosd\n")
        with patch("licigt.ingesta.reproducir.subprocess.run", return_value=salida):
            self.assertFalse(reproducir.tesseract_con_spa())
        with patch("licigt.ingesta.reproducir.subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(reproducir.tesseract_con_spa())


class DescargaTests(unittest.TestCase):
    def test_descarga_cada_url_origen_con_el_cargador_oficial(self):
        contenido = b"%PDF-1.4\nbases"
        spec = {"documentos": [{"url_origen": URL_BASES, "sha256": hashlib.sha256(contenido).hexdigest()}]}

        class Falso:
            def __init__(self):
                self.pedidos = []

            def get(self, url, limite):
                self.pedidos.append(url)
                return contenido, url

        falso = Falso()
        obtenidos = reproducir.descargar_originales(spec, fetcher=falso)
        self.assertEqual(falso.pedidos, [URL_BASES])
        self.assertEqual(obtenidos, {hashlib.sha256(contenido).hexdigest(): contenido})

    def test_rechaza_dominios_ajenos_y_redirecciones_fuera_del_igss(self):
        spec = {"documentos": [{"url_origen": "https://example.com/a.pdf", "sha256": "0" * 64}]}
        with self.assertRaisesRegex(ValueError, "igssgt.org"):
            reproducir.descargar_originales(spec, fetcher=object())
        spec = {"documentos": [{"url_origen": URL_BASES, "sha256": "0" * 64}]}

        class Redirige:
            def get(self, url, limite):
                return b"%PDF-1.4\nx", "https://example.com/a.pdf"

        with self.assertRaisesRegex(ValueError, "igssgt.org"):
            reproducir.descargar_originales(spec, fetcher=Redirige())


class PrepareCorpusTests(unittest.TestCase):
    def test_prepare_lee_la_especificacion_y_conserva_los_ids(self):
        a, b = _parches()
        with tempfile.TemporaryDirectory() as temporal, a, b:
            raiz = Path(temporal)
            spec = reproducir.generar_especificacion(_zip_de_origen(raiz))
            data = raiz / "nuevo"
            for documento in spec["documentos"]:
                carpeta = data / "descargas_igss" / documento["numero_evento"]
                carpeta.mkdir(parents=True, exist_ok=True)
                origen = raiz / "origen" / "descargas_igss" / documento["numero_evento"] / documento["sha256"]
                shutil.copy(origen.with_suffix(".pdf"), carpeta / f"{documento['sha256']}.pdf")
                (carpeta / f"{documento['sha256']}.json").write_text(json.dumps(documento["procedencia"]))
            resultados = prepare_corpus.prepare(data, spec=spec)
        self.assertEqual([r["doc_id"] for r in resultados], [d["doc_id"] for d in spec["documentos"]])

    def test_tenant_distinto_al_de_la_especificacion_falla(self):
        spec = {"tenant_id": TENANT, "documentos": []}
        with self.assertRaisesRegex(ValueError, "tenant"):
            prepare_corpus.prepare(Path("no-existe"), "otra_empresa", spec=spec)


class MakefileTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("make"), "make no está instalado")
    def test_make_corpus_sin_confirmar_solo_muestra_lo_que_haria(self):
        resultado = subprocess.run(["make", "-C", str(RAIZ), "corpus"], capture_output=True, text=True,
                                   env={"PATH": "/usr/bin:/bin"}, timeout=60)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("CONFIRMAR=1", resultado.stdout)
        self.assertIn("--descargar", resultado.stdout)


@unittest.skipUnless(ZIP_ACTUAL.is_file() and shutil.which("pdftotext"),
                     "requiere el paquete actual y poppler-utils")
class ReproducibilidadTests(unittest.TestCase):
    """Reconstruye el corpus desde los originales del ZIP vigente, sin red, y lo compara con él."""

    # Campos de tiempo de la exportación, el único margen permitido.
    CAMPOS_DE_TIEMPO = {"inventario.json": {"generated_at"}}
    CAMPOS_DE_TIEMPO_MANIFIESTO = {"reprocessed_at", "reextracted_at"}

    def test_el_paquete_reconstruido_es_identico_al_actual(self):
        spec = reproducir.cargar_especificacion()
        con_spa = reproducir.tesseract_con_spa()
        # Sin spa no se puede reproducir el texto OCR: esos documentos no se comparan (y se avisa abajo).
        omitidos = {d["doc_id"] for d in spec["documentos"] if d["paginas_ocr"]} if not con_spa else set()
        with tempfile.TemporaryDirectory() as temporal:
            salida = Path(temporal) / "empresa_demo.zip"
            reproducir.reproducir(spec, reproducir.originales_desde_zip(ZIP_ACTUAL, spec), salida, ocr=con_spa)
            actual, nuevo = _leer(ZIP_ACTUAL), _leer(salida)
        self.assertEqual(sorted(actual), sorted(nuevo))
        diferencias = []

        def del_documento(nombre):
            return any(doc_id in nombre for doc_id in omitidos)

        def lineas(paquete):
            return [l for l in paquete["chunks.jsonl"].splitlines()
                    if json.loads(l)["doc_id"] not in omitidos]

        lineas_a, lineas_n = lineas(actual), lineas(nuevo)
        if len(lineas_a) != len(lineas_n):
            diferencias.append(f"chunks.jsonl: {len(lineas_a)} líneas en el ZIP actual, {len(lineas_n)} reconstruidas")
        for posicion, (a, n) in enumerate(zip(lineas_a, lineas_n), start=1):
            ja, jn = json.loads(a), json.loads(n)
            for campo in sorted(set(ja) | set(jn)):
                if ja.get(campo) != jn.get(campo):
                    diferencias.append(f"chunks.jsonl línea {posicion} ({ja['chunk_id']}), campo {campo}: "
                                       f"{str(ja.get(campo))[:80]!r} != {str(jn.get(campo))[:80]!r}")
                    break
            if len(diferencias) > 10:
                break
        for nombre in actual:
            if nombre == "chunks.jsonl" or del_documento(nombre):
                continue
            if nombre.startswith("originales/"):
                self.assertEqual(actual[nombre], nuevo[nombre], nombre)
                continue
            esperado, obtenido = json.loads(actual[nombre]), json.loads(nuevo[nombre])
            ignorados = self.CAMPOS_DE_TIEMPO.get(nombre, set())
            if nombre.startswith("manifiestos/"):
                ignorados = self.CAMPOS_DE_TIEMPO_MANIFIESTO
            if nombre == "inventario.json":
                for paquete in (esperado, obtenido):
                    paquete["documents"] = [d for d in paquete["documents"] if d["doc_id"] not in omitidos]
                ignorados = ignorados | ({"chunks_indexables", "chunks_excluidos", "sha256_chunks_jsonl"}
                                         if omitidos else set())
            for campo in sorted((set(esperado) | set(obtenido)) - ignorados):
                if esperado.get(campo) != obtenido.get(campo):
                    diferencias.append(f"{nombre}, campo {campo}: {str(esperado.get(campo))[:100]!r} "
                                       f"!= {str(obtenido.get(campo))[:100]!r}")
        self.assertEqual(diferencias, [], "\n".join(diferencias))
        if omitidos:
            self.skipTest("Sin Tesseract con idioma spa: se comparó todo salvo los documentos con "
                          f"paginas_ocr, que no se pudieron reproducir: {sorted(omitidos)}")


if __name__ == "__main__":
    unittest.main()
