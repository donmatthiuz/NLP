"""Auditoría en JSONL por día, sin la pregunta, texto de PDF, contraseñas ni tokens."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from licigt.plataforma import auditoria


class AuditoriaTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.dir = Path(self.temporal.name) / "auditoria"
        entorno = patch.dict(os.environ, {"LICIGT_AUDITORIA_DIR": str(self.dir)})
        entorno.start()
        self.addCleanup(entorno.stop)

    def lineas(self):
        return [json.loads(l) for f in sorted(self.dir.glob("*.jsonl")) for l in f.read_text().splitlines()]

    def test_un_archivo_por_dia_con_una_linea_por_evento(self):
        auditoria.registrar("login", "ok", usuario="ana", tenant_id="empresa_demo")
        auditoria.registrar("login", "ok", usuario="ana", tenant_id="empresa_demo")
        archivos = list(self.dir.glob("*.jsonl"))
        self.assertEqual([a.name for a in archivos], [datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"])
        self.assertEqual(len(self.lineas()), 2)

    def test_consulta_solo_deja_los_campos_del_contrato(self):
        auditoria.registrar_consulta({
            "momento": "2026-11-18T10:00:00+00:00", "usuario": "ana", "tenant_id": "empresa_demo",
            "evento_id": "e1", "intencion": {"accion": "buscar", "motivo": "m", "variante": "mejorada", "x": "pregunta"},
            "herramienta": "buscar_documentos", "chunk_ids": ["c1"], "abstained": False,
            "needs_human_review": False, "validacion": "ok", "latencia_ms": 12.5, "error": None,
            "chunk_ids_citados": ["c1"], "modelo_generador": "m", "version_prompt": "v1",
            "pregunta": "TEXTO-DE-LA-PREGUNTA", "answer": "TEXTO-DE-LA-RESPUESTA",
            "citas_jev": {"texto": "TEXTO-DE-PDF"}})
        (linea,) = self.lineas()
        self.assertEqual((linea["accion"], linea["resultado"]), ("consulta", "ok"))
        self.assertEqual(linea["intencion"], {"accion": "buscar", "motivo": "m", "variante": "mejorada"})
        self.assertEqual(linea["chunk_ids"], ["c1"])
        texto = json.dumps(linea)
        for prohibido in ("TEXTO-DE-LA-PREGUNTA", "TEXTO-DE-LA-RESPUESTA", "TEXTO-DE-PDF"):
            self.assertNotIn(prohibido, texto)

    def test_carga_solo_deja_los_campos_del_contrato_y_marca_ingesta(self):
        auditoria.registrar_carga({
            "tenant_id": "empresa_demo", "evento_id": "e1", "doc_id": "d1", "hash_sha256": "h1",
            "status": "requiere_revision", "paginas_legibles": 1, "paginas_total": 2,
            "warnings": ["Hay páginas incompletas o ilegibles"],
            "created_at": "2026-11-19T10:00:00+00:00", "reextracted_at": "2026-11-19T11:00:00+00:00",
            "texto": "TEXTO-DE-PDF", "object_uri": "file:///ruta/local/bases.pdf",
            "chunks": [{"texto": "TEXTO-DE-FRAGMENTO"}]})
        (linea,) = self.lineas()
        self.assertEqual((linea["accion"], linea["resultado"]), ("ingesta", "requiere_revision"))
        self.assertEqual((linea["doc_id"], linea["paginas_legibles"], linea["paginas_total"]),
                         ("d1", 1, 2))
        self.assertEqual(linea["reextracted_at"], "2026-11-19T11:00:00+00:00")
        texto = json.dumps(linea)
        for prohibido in ("TEXTO-DE-PDF", "TEXTO-DE-FRAGMENTO", "file:///ruta/local"):
            self.assertNotIn(prohibido, texto)

    def test_carga_no_guarda_usuario_ni_credenciales_en_claro(self):
        auditoria.registrar_carga({"tenant_id": "t", "evento_id": "e1", "status": "completo",
                                   "usuario": "ana", "password": "SECRETO", "token": "TOKEN-X"})
        (linea,) = self.lineas()
        texto = json.dumps(linea)
        for prohibido in ("ana", "SECRETO", "TOKEN-X"):
            self.assertNotIn(prohibido, texto)
        self.assertNotIn("usuario", linea)

    def test_resultado_es_el_error_si_lo_hay(self):
        auditoria.registrar_consulta({"usuario": "ana", "tenant_id": "t", "error": "tiempo_agotado"})
        auditoria.registrar_lista({"usuario": "ana", "tenant_id": "t", "accion": "lista_alta",
                                   "evento_id": "e", "item_ids": ["i"], "error": "cita_no_valida"})
        a, b = self.lineas()
        self.assertEqual((a["accion"], a["resultado"]), ("consulta", "tiempo_agotado"))
        self.assertEqual((b["accion"], b["resultado"], b["item_ids"]), ("lista_alta", "cita_no_valida", ["i"]))

    def test_propuesta_de_lista_se_registra_como_tal(self):
        auditoria.registrar_consulta({"usuario": "ana", "tenant_id": "t", "intencion": {"accion": "proponer_lista"}})
        self.assertEqual(self.lineas()[0]["accion"], "proponer_lista")

    def test_usuario_de_login_fallido_va_con_hash(self):
        auditoria.registrar_login_fallido("ana.perez")
        (linea,) = self.lineas()
        self.assertEqual((linea["accion"], linea["resultado"], linea["tenant_id"]), ("login", "credenciales_invalidas", None))
        self.assertTrue(linea["usuario"].startswith("hmac:"))
        self.assertNotIn("ana.perez", json.dumps(linea))

    def test_el_hash_del_login_fallido_lleva_clave_y_no_es_sha256_simple(self):
        import hashlib, hmac
        clave = self.dir.parent / "sesion.key"
        clave.write_text("k" * 64)
        with patch.dict(os.environ, {"LICIGT_SESION_CLAVE_ARCHIVO": str(clave)}):
            auditoria.registrar_login_fallido("ana.perez")
        (linea,) = self.lineas()
        esperado = hmac.new(b"k" * 64, b"ana.perez", hashlib.sha256).hexdigest()[:16]
        self.assertEqual(linea["usuario"], f"hmac:{esperado}")
        self.assertNotIn(hashlib.sha256(b"ana.perez").hexdigest()[:16], json.dumps(linea))

    def test_una_falla_al_escribir_no_rompe_a_quien_llama(self):
        with patch.dict(os.environ, {"LICIGT_AUDITORIA_DIR": "/proc/no-se-puede/auditoria"}):
            auditoria.registrar("login", "ok", usuario="ana", tenant_id="t")

    def test_una_falla_al_escribir_deja_un_aviso_sin_datos_sensibles(self):
        with patch.dict(os.environ, {"LICIGT_AUDITORIA_DIR": "/proc/no-se-puede/auditoria"}):
            with self.assertLogs("licigt.plataforma.auditoria", level="WARNING") as cap:
                auditoria.registrar("login", "ok", usuario="ana.perez", tenant_id="empresa_secreta")
        texto = "\n".join(cap.output)
        self.assertIn("auditoría", texto)
        for prohibido in ("ana.perez", "empresa_secreta"):
            self.assertNotIn(prohibido, texto)

    def test_ninguna_linea_lleva_el_usuario_en_claro(self):
        auditoria.registrar("login", "ok", usuario="ana.perez", tenant_id="empresa_demo")
        auditoria.registrar_consulta({"usuario": "ana.perez", "tenant_id": "empresa_demo"})
        auditoria.registrar_lista({"usuario": "ana.perez", "tenant_id": "empresa_demo", "accion": "lista_alta"})
        auditoria.registrar_login_fallido("ana.perez")
        lineas = self.lineas()
        self.assertEqual(len(lineas), 4)
        for linea in lineas:
            self.assertNotIn("ana.perez", json.dumps(linea))
            self.assertRegex(linea["usuario"], r"^hmac:[0-9a-f]{16}$")
        self.assertEqual(len({l["usuario"] for l in lineas}), 1)  # el mismo usuario, la misma huella
        self.assertEqual(lineas[0]["tenant_id"], "empresa_demo")  # el tenant_id se mantiene

    def test_sin_clave_de_sesion_el_usuario_es_una_constante(self):
        with patch.dict(os.environ, {"LICIGT_SESION_CLAVE_ARCHIVO": str(self.dir.parent / "no-existe.key")}):
            auditoria.registrar("login", "ok", usuario="ana.perez")
            auditoria.registrar("login", "ok", usuario="luis")
        self.assertEqual({l["usuario"] for l in self.lineas()}, {"hmac:sin-clave"})

    def test_sin_usuario_queda_nulo(self):
        auditoria.registrar("login", "credenciales_invalidas")
        self.assertIsNone(self.lineas()[0]["usuario"])


if __name__ == "__main__":
    unittest.main()
