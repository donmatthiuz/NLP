"""R2C: dispositivo y dtype, suficiencia e interfaces pedidas por el rol 3 (resolver_evento, obtener_fragmentos)."""

import os
import unittest
from unittest import mock

from licigt.recuperacion import busqueda, indice
from licigt.recuperacion.busqueda import Contexto, buscar, obtener_fragmentos, resolver_evento


CARGAR_REAL = indice.cargar


def entorno(**kw):
    return mock.patch.dict(os.environ, {k: v for k, v in kw.items()}, clear=False)


class DispositivoTests(unittest.TestCase):
    def setUp(self):
        for v in ("LICIGT_RECUPERACION_DISPOSITIVO", "LICIGT_RECUPERACION_DTYPE"):
            os.environ.pop(v, None)

    def test_auto_usa_cuda_si_existe(self):
        with mock.patch.object(indice, "_cuda_disponible", return_value=True):
            self.assertEqual(indice.dispositivo(), "cuda")
        with mock.patch.object(indice, "_cuda_disponible", return_value=False):
            self.assertEqual(indice.dispositivo(), "cpu")

    def test_cuda_pedida_sin_cuda_cae_a_cpu_con_aviso(self):
        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="cuda"), \
                mock.patch.object(indice, "_cuda_disponible", return_value=False), \
                self.assertLogs("licigt.recuperacion.indice", "WARNING"):
            self.assertEqual(indice.dispositivo(), "cpu")

    def test_valor_invalido(self):
        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="tpu"), self.assertRaises(ValueError):
            indice.dispositivo()
        with entorno(LICIGT_RECUPERACION_DTYPE="bfloat16"), self.assertRaises(ValueError):
            indice.dtype_modelo("cuda")

    def test_dtype_por_defecto_solo_fp16_en_cuda(self):
        self.assertEqual(indice.dtype_modelo("cuda"), "float16")
        self.assertEqual(indice.dtype_modelo("cpu"), "float32")
        with entorno(LICIGT_RECUPERACION_DTYPE="float32"):
            self.assertEqual(indice.dtype_modelo("cuda"), "float32")

    def test_se_pasan_device_y_dtype_al_modelo(self):
        creados = []

        class Falso:
            def __init__(self, nombre, **kw):
                creados.append((nombre, kw))

        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="cuda", LICIGT_RECUPERACION_DTYPE="float16"), \
                mock.patch.object(indice, "_cuda_disponible", return_value=True):
            indice.cargar(Falso, "m", revision="r")
        kw = creados[0][1]
        self.assertEqual((kw["device"], kw["revision"]), ("cuda", "r"))
        self.assertEqual(list(kw["model_kwargs"].values()), ["float16"])

    def test_sin_memoria_en_cuda_cae_a_cpu_sin_abortar(self):
        intentos = []

        class SinMemoria:
            def __init__(self, nombre, device, model_kwargs, **kw):
                intentos.append((device, model_kwargs))
                if device == "cuda":
                    raise RuntimeError("CUDA out of memory")

        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="cuda"), \
                mock.patch.object(indice, "_cuda_disponible", return_value=True), \
                self.assertLogs("licigt.recuperacion.indice", "WARNING"):
            indice.cargar(SinMemoria, "m")
        self.assertEqual([d for d, _ in intentos], ["cuda", "cpu"])
        self.assertEqual(list(intentos[1][1].values()), ["float32"])

    def test_error_en_cpu_se_propaga(self):
        class Roto:
            def __init__(self, *a, **kw):
                raise RuntimeError("otro")

        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="cpu"), self.assertRaises(RuntimeError):
            indice.cargar(Roto, "m")


class SinMemoriaTests(unittest.TestCase):
    def setUp(self):
        indice._EN_CPU.clear()
        indice.modelo.cache_clear()
        self.addCleanup(indice._EN_CPU.clear)
        self.addCleanup(indice.modelo.cache_clear)
        self.cargas = []

        class Modelo:
            def __init__(m, device):
                m.device = device

            def encode(m, texto):
                if m.device == "cuda":
                    raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
                return [0.0]

        def cargar(clase, nombre, **kw):
            disp = "cpu" if nombre in indice._EN_CPU else "cuda"
            self.cargas.append(disp)
            return Modelo(disp)

        p = mock.patch.object(indice, "cargar", cargar)
        p.start()
        self.addCleanup(p.stop)

    def test_recarga_en_cpu_una_vez_y_sigue_en_cpu(self):
        n = indice.MODELO_BASE
        with self.assertLogs("licigt.recuperacion.indice", "WARNING"):
            r = indice.ejecutar(n, indice.modelo, lambda m: m.encode("x"), n)
        self.assertEqual(r, [0.0])
        self.assertEqual(self.cargas, ["cuda", "cpu"])
        indice.ejecutar(n, indice.modelo, lambda m: m.encode("y"), n)
        self.assertEqual(self.cargas, ["cuda", "cpu"])  # ya en caché, sin recargar

    def test_otros_errores_no_se_reintentan(self):
        def falla(m):
            raise RuntimeError("otra cosa")
        with self.assertRaises(RuntimeError):
            indice.ejecutar(indice.MODELO_BASE, indice.modelo, falla, indice.MODELO_BASE)
        self.assertEqual(self.cargas, ["cuda"])

    def test_sin_memoria_tambien_en_cpu_se_propaga(self):
        indice._EN_CPU.add(indice.MODELO_BASE)
        def falla(m):
            raise RuntimeError("out of memory")
        with self.assertRaises(RuntimeError):
            indice.ejecutar(indice.MODELO_BASE, indice.modelo, falla, indice.MODELO_BASE)

    def test_importar_cae_a_cpu_ante_oom(self):
        chunk = {"chunk_id": "c", "doc_id": "d", "tenant_id": "t", "evento_id": "e", "numero_evento": "n",
                 "tipo_documento": "bases", "version_ingesta": 1, "pagina_inicio": 1, "pagina_fin": 1,
                 "texto": "hola", "url_origen": "https://x"}
        paquete = ({"documents": [], "tenant_id": "t"}, [chunk], {})
        modelos = {}

        class Falso:
            def __init__(m, device):
                m.device = device

            def encode(m, textos, **kw):
                if m.device == "cuda":
                    raise RuntimeError("CUDA out of memory")
                return [[0.0]] * len(textos)

        def cargar(clase, nombre, **kw):
            disp = "cpu" if nombre in indice._EN_CPU else "cuda"
            return modelos.setdefault((nombre, disp), Falso(disp))

        with mock.patch.object(indice, "leer_paquete", return_value=paquete), \
                mock.patch.object(indice, "cargar", cargar), \
                self.assertLogs("licigt.recuperacion.indice", "WARNING"):
            r = indice.importar("x.zip", conn=mock.MagicMock())
        self.assertEqual(r["mejorada"], 1)
        self.assertIn(indice.MODELO_MEJORADA, indice._EN_CPU)

    def test_dos_hilos_con_oom_recargan_una_vez(self):
        import threading
        n = indice.MODELO_BASE
        barrera = threading.Barrier(2)
        resultados, errores = [], []

        def hilo():
            try:
                def op(m):
                    r = m.encode("x")
                    return r
                modelo_ = indice.modelo(n)  # ambos toman el modelo en cuda
                barrera.wait(timeout=5)
                resultados.append(indice.ejecutar(n, indice.modelo, op, n))
            except Exception as exc:
                errores.append(exc)

        with self.assertLogs("licigt.recuperacion.indice", "WARNING") as cap:
            hs = [threading.Thread(target=hilo) for _ in range(2)]
            [h.start() for h in hs]
            [h.join(10) for h in hs]
        self.assertEqual(errores, [])
        self.assertEqual(resultados, [[0.0], [0.0]])
        self.assertEqual(sum("se recarga en CPU" in m for m in cap.output), 1)

    def test_en_cpu_pero_cache_en_cuda_reintenta_una_vez(self):
        n = indice.MODELO_BASE
        indice.modelo(n)  # queda en caché en cuda
        indice._EN_CPU.add(n)
        self.assertEqual(indice.ejecutar(n, indice.modelo, lambda m: m.encode("x"), n), [0.0])
        self.assertEqual(self.cargas, ["cuda", "cpu"])

    def test_cargar_libera_memoria_fuera_del_except(self):
        estado = []

        class SinMemoria:
            def __init__(self, nombre, device, model_kwargs, **kw):
                if device == "cuda":
                    raise RuntimeError("CUDA out of memory")

        def gc_(*a):
            import sys
            estado.append(sys.exc_info()[0])
            return 0

        with entorno(LICIGT_RECUPERACION_DISPOSITIVO="cuda"), \
                mock.patch.object(indice, "_cuda_disponible", return_value=True), \
                mock.patch.object(indice.gc, "collect", gc_), self.assertLogs("licigt.recuperacion.indice", "WARNING"):
            CARGAR_REAL(SinMemoria, "m")
        self.assertEqual(estado, [None])


class BarridoTests(unittest.TestCase):
    def test_barrido_cuenta_aciertos_de_suficiencia(self):
        from licigt.recuperacion.evaluar import barrido
        puntos = [(0.001, False), (0.006, True), (0.5, True)]
        self.assertEqual(dict(barrido(puntos)), {0.0: 2, 0.001: 2, 0.006: 3, 0.5: 2})


class SuficienciaTests(unittest.TestCase):
    def test_solo_cuenta_el_puntaje_del_primer_resultado(self):
        umbral = busqueda.UMBRAL["mejorada"]
        self.assertTrue(busqueda.suficiente("mejorada", [{"score": umbral, "texto": ""}]))
        self.assertFalse(busqueda.suficiente("mejorada", [{"score": umbral - 0.001, "texto": ""}]))
        self.assertFalse(busqueda.suficiente("mejorada", []))

    def test_sin_respaldo_por_identificadores(self):
        # Casos del adversario: el texto repite el numeral o el NOG de la pregunta, pero el puntaje es bajo.
        self.assertFalse(busqueda.suficiente("mejorada", [{"score": 0.001, "texto": "subnumeral 2.7 Listado"}]))
        self.assertFalse(busqueda.suficiente("mejorada", [{"score": 0.001, "texto": "NOG 19595840 precio adjudicado"}]))
        self.assertFalse(hasattr(busqueda, "IDENTIFICADOR"))


class _Cur:
    def __init__(self, filas):
        self.filas = filas

    def fetchone(self):
        return self.filas[0] if self.filas else None

    def fetchall(self):
        return self.filas


class _Conn:
    """Doble de la conexión: guarda las consultas y devuelve filas predefinidas."""
    def __init__(self, filas):
        self.filas, self.consultas, self.cierres = filas, [], 0

    def close(self):
        self.cierres += 1

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def transaction(self):
        return mock.MagicMock()

    def execute(self, sql, params=None):
        self.consultas.append((sql, params))
        return _Cur(self.filas if "FROM" in sql else [])


class InterfacesUnidadTests(unittest.TestCase):
    def test_resolver_evento_filtra_por_empresa(self):
        conn = _Conn([("abc",)])
        self.assertEqual(resolver_evento(Contexto("e1"), "222-IGSS-2023", conn=conn), "abc")
        sql, params = conn.consultas[-1]
        self.assertIn("tenant_id", sql)
        self.assertEqual(params, ("e1", "222-IGSS-2023"))
        self.assertIsNone(resolver_evento(Contexto("e1"), "x", conn=_Conn([])))

    def test_cierra_la_conexion_que_abre(self):
        for llamada in (lambda c: resolver_evento(Contexto("e1"), "x"),
                        lambda c: obtener_fragmentos(Contexto("e1"), "ev", ["a"]),
                        lambda c: busqueda.comparar_versiones(Contexto("e1"), "ev", "p")):
            conn = _Conn([])
            with mock.patch.object(busqueda, "conectar", return_value=conn):
                llamada(conn)
            self.assertEqual(conn.cierres, 1)

    def test_no_cierra_la_conexion_recibida(self):
        conn = _Conn([("abc",)])
        resolver_evento(Contexto("e1"), "x", conn=conn)
        obtener_fragmentos(Contexto("e1"), "ev", ["a"], conn=_Conn([]))
        self.assertEqual(conn.cierres, 0)

    def test_obtener_fragmentos_acepta_fragmento_recuperado(self):
        from licigt.consulta.lectura import FragmentoRecuperado
        fila = dict(zip(busqueda.CAMPOS, ("c", "d", "bases", 1, 1, 1, "s", "t", "https://x", None)), _score=0)
        conn = _Conn([tuple(fila[c] for c in busqueda.CAMPOS) + (0,)])
        f = obtener_fragmentos(Contexto("e1"), "ev", ["c"], conn=conn)[0]
        self.assertEqual(f["score"], 0.0)
        FragmentoRecuperado(**f)

    def test_obtener_fragmentos_sin_ids_no_consulta(self):
        conn = _Conn([])
        self.assertEqual(obtener_fragmentos(Contexto("e1"), "ev", [], conn=conn), [])
        self.assertEqual(conn.consultas, [])

    def test_obtener_fragmentos_filtra_empresa_y_evento(self):
        conn = _Conn([])
        obtener_fragmentos(Contexto("e1"), "ev", ["a"], conn=conn)
        sql, params = conn.consultas[-1]
        self.assertIn("tenant_id", sql)
        self.assertIn("evento_id", sql)
        self.assertEqual(params["t"], "e1")
        self.assertEqual(params["e"], "ev")


class InterfacesIntegracionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    @classmethod
    def setUpClass(cls):
        try:
            cls.conn = indice.conectar()
            eventos = dict(cls.conn.execute("SELECT DISTINCT numero_evento, evento_id FROM documentos").fetchall())
        except Exception as exc:
            raise unittest.SkipTest(f"Postgres no disponible o vacío: {exc}")
        if "222-IGSS-2023" not in eventos:
            cls.conn.close()
            raise unittest.SkipTest("Paquete no importado")
        cls.e222, cls.e399 = eventos["222-IGSS-2023"], eventos["399-IGSS-2026"]
        cls.ctx = Contexto("empresa_demo")

    def test_resolver_por_numero_y_por_id(self):
        self.assertEqual(resolver_evento(self.ctx, "222-IGSS-2023", conn=self.conn), self.e222)
        self.assertEqual(resolver_evento(self.ctx, self.e222, conn=self.conn), self.e222)
        self.assertIsNone(resolver_evento(self.ctx, "no-existe", conn=self.conn))
        self.assertIsNone(resolver_evento(Contexto("otra_empresa"), "222-IGSS-2023", conn=self.conn))

    def test_obtener_fragmentos_mismos_campos_y_aislamiento(self):
        r = buscar(self.ctx, self.e222, "fecha y hora para la recepción de ofertas", conn=self.conn)
        ids = [f["chunk_id"] for f in r["fragmentos"]]
        got = obtener_fragmentos(self.ctx, self.e222, ids, conn=self.conn)
        self.assertEqual([f["chunk_id"] for f in got], ids)
        for f, orig in zip(got, r["fragmentos"]):
            self.assertEqual({k: v for k, v in orig.items() if k in busqueda.CAMPOS}, {k: v for k, v in f.items() if k != "score"})
        ajeno = buscar(self.ctx, self.e399, "cronograma de actividades", conn=self.conn)["fragmentos"][0]["chunk_id"]
        self.assertEqual(obtener_fragmentos(self.ctx, self.e222, [ajeno], conn=self.conn), [])
        self.assertEqual(obtener_fragmentos(Contexto("otra_empresa"), self.e222, ids, conn=self.conn), [])

    def test_aislamiento_contra_empresa_b(self):
        eventos = dict(self.conn.execute(
            "SELECT DISTINCT numero_evento, evento_id FROM documentos WHERE tenant_id = 'empresa_b'").fetchall())
        if "363-IGSS-2026" not in eventos:
            self.skipTest("empresa_b no está importada")
        e363 = eventos["363-IGSS-2026"]
        ajeno = self.conn.execute("SELECT chunk_id FROM fragmentos WHERE tenant_id = 'empresa_b' AND evento_id = %s LIMIT 1",
                                  (e363,)).fetchone()[0]
        self.assertEqual(obtener_fragmentos(self.ctx, e363, [ajeno], conn=self.conn), [])
        self.assertIsNone(resolver_evento(Contexto("empresa_b"), "222-IGSS-2023", conn=self.conn))

    def test_cobertura_incompleta_lleva_warnings(self):
        r = buscar(self.ctx, self.e222, "fecha y hora para la recepción de ofertas", conn=self.conn)
        cob = [a for a in r["alertas"] if a["tipo"] == "cobertura_incompleta"]
        self.assertTrue(cob)
        for a in cob:
            self.assertIsInstance(a["warnings"], list)
        self.assertTrue(any(a["warnings"] for a in cob))


if __name__ == "__main__":
    unittest.main()
