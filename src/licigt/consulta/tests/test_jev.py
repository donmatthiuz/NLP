"""Cliente SDK simulado, configuración y frecuencia sin credenciales reales."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from licigt.consulta.config import Configuracion, obtener_configuracion
from licigt.consulta.jev import ClienteJevSdk, FallaJev, LimitadorFrecuencia
from licigt.consulta.preguntas_jev import PREGUNTAS_ENTRADA
from test_enrutador import respuesta_jev


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.esperas = []

    def leer(self):
        return self.ahora

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.ahora += segundos


class JevTests(unittest.TestCase):
    def test_configuracion_entorno_una_vez(self):
        obtener_configuracion.cache_clear()
        self.addCleanup(obtener_configuracion.cache_clear)
        with patch.dict(os.environ, {"LICIGT_ENRUTADOR": "jev", "LICIGT_JEV_REINTENTOS": "1",
                                     "LICIGT_JEV_MAX_SOLICITUDES_SEG": "2"}, clear=True):
            config = obtener_configuracion()
            os.environ["LICIGT_ENRUTADOR"] = "reglas"
            self.assertIs(config, obtener_configuracion())
            self.assertEqual(config.enrutador, "jev")
            self.assertEqual(config.reintentos, 1)
            self.assertEqual(config.max_solicitudes_seg, 2)
            self.assertEqual(config.modelo, "jev-1.14.0")
        with patch.dict(os.environ, {}, clear=True):
            obtener_configuracion.cache_clear()
            self.assertEqual(obtener_configuracion().enrutador, "reglas")

    def test_configuracion_rechaza_valores_invalidos(self):
        for cambios in ({"enrutador": "otro"}, {"modelo": "jev-latest"}, {"modelo": " "},
                        {"reintentos": -1}, {"tiempo_espera": 0}, {"max_solicitudes_seg": 0},
                        {"max_solicitudes_seg": float("nan")}, {"espera_frecuencia": -1}):
            with self.subTest(cambios=cambios), self.assertRaises(ValidationError):
                Configuracion(**cambios)

    def test_cubeta_permite_rafaga_y_repone(self):
        reloj = RelojFalso()
        limite = LimitadorFrecuencia(2, 1, reloj.leer, reloj.dormir)
        limite.adquirir()
        limite.adquirir()
        self.assertEqual(reloj.esperas, [])
        limite.adquirir()
        self.assertAlmostEqual(reloj.ahora, 0.5)
        reloj.ahora += 20
        limite.adquirir()
        limite.adquirir()
        limite.adquirir()
        self.assertAlmostEqual(reloj.esperas[-1], 0.5)

    def test_cubeta_agota_espera(self):
        reloj = RelojFalso()
        limite = LimitadorFrecuencia(1, 0.2, reloj.leer, reloj.dormir)
        limite.adquirir()
        with self.assertRaises(FallaJev) as error:
            limite.adquirir()
        self.assertEqual(error.exception.codigo, "limite_frecuencia")
        self.assertAlmostEqual(reloj.ahora, 0.2)

    def test_cubeta_no_admite_espera_excedida_por_planificador(self):
        reloj = RelojFalso()
        limite = LimitadorFrecuencia(1, 1, reloj.leer, lambda segundos: reloj.dormir(segundos + 1))
        limite.adquirir()
        with self.assertRaises(FallaJev):
            limite.adquirir()

    def preparar_sdk(self, carpeta):
        class ErrorSdk(Exception):
            pass
        class ErrorApi(ErrorSdk):
            pass
        class ErrorTiempo(ErrorSdk, TimeoutError):
            pass
        respuesta = respuesta_jev()
        salida = SimpleNamespace(
            answers={k: SimpleNamespace(model_dump=lambda v=v, **opciones: v)
                     for k, v in respuesta.respuestas.items()},
            model=respuesta.modelo, request_id="prueba",
            usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        salida.raw_http_response = SimpleNamespace(json=lambda: {
            "model": respuesta.modelo, "answers": respuesta.respuestas,
            "usage": {"input_tokens": 100, "output_tokens": 20}, "campo_futuro": "conservar"})
        cliente = Mock()
        cliente.system_one.return_value = salida
        sdk = SimpleNamespace(TypeSafeClient=Mock(return_value=cliente), RetryPolicy=Mock(),
                              TypeSafeError=ErrorSdk, TypeSafeAPIError=ErrorApi)
        archivo = Path(carpeta) / "clave-ficticia"
        archivo.write_text("clave-ficticia-para-pruebas\n")
        config = Configuracion(archivo_clave=archivo)
        return sdk, cliente, config, (ErrorSdk, ErrorApi, ErrorTiempo)

    def test_sdk_parametros_y_metadatos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sdk, cliente, config, _ = self.preparar_sdk(carpeta)
            with patch.dict("sys.modules", {"typesafe_sdk": sdk}):
                adaptador = ClienteJevSdk(config)
                respuesta = adaptador.preguntar({"pregunta": "código"}, PREGUNTAS_ENTRADA)
                adaptador.cerrar()
        opciones = sdk.TypeSafeClient.call_args.kwargs
        self.assertEqual(opciones["api_key"], "clave-ficticia-para-pruebas")
        self.assertEqual(opciones["model"], "jev-1.14.0")
        self.assertEqual(opciones["timeout"], 5)
        self.assertEqual(sdk.RetryPolicy.call_args.kwargs["max_retries"], 2)
        self.assertEqual(sdk.RetryPolicy.call_args.kwargs["timeout"], 5)
        self.assertEqual(cliente.system_one.call_args.kwargs,
                         {"state": {"pregunta": "código"}, "questions": PREGUNTAS_ENTRADA})
        self.assertEqual((respuesta.modelo, respuesta.request_id, respuesta.tokens_entrada,
                          respuesta.tokens_salida), ("jev-1.14.0", "prueba", 100, 20))
        self.assertEqual(respuesta.original, cliente.system_one.return_value.raw_http_response.json())
        cliente.close.assert_called_once()

    def test_sdk_errores_sin_texto_privado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sdk, cliente, config, errores = self.preparar_sdk(carpeta)
            with patch.dict("sys.modules", {"typesafe_sdk": sdk}):
                adaptador = ClienteJevSdk(config)
                for tipo, codigo in zip(errores, ("sdk", "api", "tiempo_agotado")):
                    cliente.system_one.side_effect = tipo("pregunta confidencial")
                    with self.subTest(tipo=tipo), self.assertRaises(FallaJev) as error:
                        adaptador.preguntar({"pregunta": "privada"}, PREGUNTAS_ENTRADA)
                    self.assertEqual(str(error.exception), codigo)
                    self.assertTrue(error.exception.__suppress_context__)
                sdk.TypeSafeClient.side_effect = errores[0]("clave privada")
                with self.assertRaises(FallaJev) as error:
                    ClienteJevSdk(config)
                self.assertEqual(str(error.exception), "sdk")

    def test_sdk_incompletas_y_probabilidades_invalidas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sdk, cliente, config, _ = self.preparar_sdk(carpeta)
            with patch.dict("sys.modules", {"typesafe_sdk": sdk}):
                adaptador = ClienteJevSdk(config)
                for respuestas in ({}, {"inyeccion": {"type": "noul", "noul": 2}}):
                    cliente.system_one.return_value.answers = {
                        k: SimpleNamespace(model_dump=lambda v=v, **opciones: v) for k, v in respuestas.items()}
                    with self.subTest(respuestas=respuestas), self.assertRaises(FallaJev) as error:
                        adaptador.preguntar({"pregunta": "código"}, PREGUNTAS_ENTRADA)
                    self.assertEqual(error.exception.codigo, "respuesta_incompleta")

    def test_clave_ausente_controlada(self):
        with tempfile.TemporaryDirectory() as carpeta:
            sdk, _, config, _ = self.preparar_sdk(carpeta)
            config = config.model_copy(update={"archivo_clave": Path(carpeta) / "ausente"})
            with patch.dict("sys.modules", {"typesafe_sdk": sdk}), self.assertRaises(FallaJev) as error:
                ClienteJevSdk(config)
            self.assertEqual(error.exception.codigo, "clave_no_disponible")

    def test_sdk_ausente_controlado(self):
        with patch.dict("sys.modules", {"typesafe_sdk": None}), self.assertRaises(FallaJev) as error:
            ClienteJevSdk(Configuracion())
        self.assertEqual(error.exception.codigo, "sdk_no_disponible")
