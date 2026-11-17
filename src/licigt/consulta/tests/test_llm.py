"""Cliente OpenAI compatible probado con SDK falso, sin leer llaves reales."""

import json
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from licigt.consulta.config import ConfiguracionLlm, obtener_configuracion_llm
from licigt.consulta.generacion import esquema_salida
from licigt.consulta.llm import ClienteGeneradorOpenAI, FallaGenerador


class ErrorConexion(Exception):
    pass


class ErrorTiempo(ErrorConexion):
    pass


class ErrorApi(Exception):
    pass


def sdk_falso():
    crear = Mock(return_value=SimpleNamespace(model="modelo-resuelto", choices=[
        SimpleNamespace(message=SimpleNamespace(content='{"abstener":true}', refusal=None))]))
    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear)), close=Mock())
    return SimpleNamespace(OpenAI=Mock(return_value=cliente), APITimeoutError=ErrorTiempo,
                           APIConnectionError=ErrorConexion, APIStatusError=ErrorApi), crear


class LlmTests(unittest.TestCase):
    def tearDown(self):
        obtener_configuracion_llm.cache_clear()

    def test_perfiles_y_variables(self):
        for perfil, url, modelo in [("local", "http://127.0.0.1:8080/v1", "qwen3.5-9b"),
                                    ("openai", "https://api.openai.com/v1", "gpt-4.1-mini")]:
            with self.subTest(perfil=perfil), patch.dict(os.environ, {"LICIGT_LLM": perfil}, clear=True):
                obtener_configuracion_llm.cache_clear()
                c = obtener_configuracion_llm()
                self.assertEqual((c.perfil, c.url, c.modelo), (perfil, url, modelo))
                self.assertEqual((c.tiempo_espera, c.max_tokens, c.semilla, c.max_caracteres_evidencia),
                                 (20, 3072, 42, 36000))
        env = {"LICIGT_LLM": "openai", "LICIGT_LLM_URL": "http://servidor/v1",
               "LICIGT_LLM_MODELO": "personalizado", "LICIGT_LLM_API_KEY_FILE": "/tmp/llave-falsa",
               "LICIGT_LLM_TIEMPO_ESPERA": "3", "LICIGT_LLM_MAX_TOKENS": "50",
               "LICIGT_LLM_SEMILLA": "9", "LICIGT_LLM_MAX_CARACTERES_EVIDENCIA": "400"}
        with patch.dict(os.environ, env, clear=True):
            obtener_configuracion_llm.cache_clear()
            c = obtener_configuracion_llm()
            self.assertEqual((c.url, c.modelo, c.archivo_clave),
                             ("http://servidor/v1", "personalizado", Path("/tmp/llave-falsa")))
            self.assertEqual((c.tiempo_espera, c.max_tokens, c.semilla, c.max_caracteres_evidencia), (3, 50, 9, 400))
        for campos in ({"perfil": "otro"}, {"tiempo_espera": 0}, {"max_tokens": -1},
                       {"max_caracteres_evidencia": 0}, {"tiempo_espera": float("nan")}):
            with self.assertRaises(ValidationError):
                ConfiguracionLlm(**campos)

    def test_llamada_estricta_y_local_no_lee_llave(self):
        sdk, crear = sdk_falso()
        esquema = esquema_salida(["F1", "F2"])
        for perfil in ("local", "openai"):
            with self.subTest(perfil=perfil), patch.dict(sys.modules, {"openai": sdk}), \
                    patch.object(Path, "read_text", return_value="llave-de-prueba\n") as leer:
                c = ClienteGeneradorOpenAI(ConfiguracionLlm(perfil=perfil))
                self.assertEqual(c.generar([{"role": "user", "content": "documentos públicos"}], esquema),
                                 '{"abstener":true}')
                argumentos = crear.call_args.kwargs
                self.assertEqual(argumentos["temperature"], 0)
                self.assertEqual(argumentos["seed"], 42)
                self.assertEqual(argumentos["max_tokens"], 3072)
                enviado = argumentos["response_format"]["json_schema"]["schema"]
                self.assertEqual(argumentos["response_format"]["type"], "json_schema")
                self.assertEqual(argumentos["response_format"]["json_schema"]["name"], "salida_licigt")
                self.assertIs(argumentos["response_format"]["json_schema"]["strict"], True)
                if perfil == "local":
                    self.assertEqual(enviado, esquema)
                self.assertEqual(sdk.OpenAI.call_args.kwargs["timeout"], 20)
                self.assertEqual(sdk.OpenAI.call_args.kwargs["max_retries"], 0)
                self.assertEqual(c.modelo_generador, "modelo-resuelto")
                self.assertEqual(c.perfil, perfil)
                if perfil == "local":
                    leer.assert_not_called()
                    self.assertEqual(argumentos["extra_body"], {"chat_template_kwargs": {"enable_thinking": False}})
                else:
                    leer.assert_called_once()
                    self.assertNotIn("extra_body", argumentos)
                c.cerrar()

    def test_c9_respuesta_cortada_es_un_error_propio(self):
        sdk, crear = sdk_falso()
        crear.return_value = SimpleNamespace(model="m", choices=[SimpleNamespace(
            finish_reason="length", message=SimpleNamespace(content='{"abstener": fal', refusal=None))])
        with patch.dict(sys.modules, {"openai": sdk}):
            c = ClienteGeneradorOpenAI(ConfiguracionLlm())
            with self.assertRaises(FallaGenerador) as fallo:
                c.generar([], esquema_salida(["F1"]))
        self.assertEqual(fallo.exception.codigo, "respuesta_cortada")
        self.assertNotIn("abstener", str(fallo.exception))

    def test_c9_semilla_extra_cambia_la_semilla_enviada(self):
        sdk, crear = sdk_falso()
        with patch.dict(sys.modules, {"openai": sdk}):
            c = ClienteGeneradorOpenAI(ConfiguracionLlm(semilla=42))
            c.generar([], esquema_salida(["F1"]))
            c.generar([], esquema_salida(["F1"]), semilla_extra=1)
        self.assertEqual([x.kwargs["seed"] for x in crear.call_args_list], [42, 43])

    def test_a7_openai_no_envia_longitud_ni_rangos_numericos(self):
        sdk, crear = sdk_falso()
        esquema = esquema_salida(["F1", "F2"])
        copia = deepcopy(esquema)
        with patch.dict(sys.modules, {"openai": sdk}), \
                patch.object(Path, "read_text", return_value="llave-de-prueba\n"):
            ClienteGeneradorOpenAI(ConfiguracionLlm(perfil="openai")).generar([], esquema)
        enviado = crear.call_args.kwargs["response_format"]["json_schema"]["schema"]
        texto = json.dumps(enviado)
        self.assertNotIn("minLength", texto)
        self.assertNotIn("maxLength", texto)
        self.assertNotIn('"minimum"', texto)
        self.assertNotIn('"maximum"', texto)
        self.assertIn('"Dato"', texto)
        self.assertIn("minItems", texto)
        self.assertIn("maxItems", texto)
        self.assertIn('"enum": ["F1", "F2"]', texto)
        self.assertEqual(esquema, copia)
        self.assertIn("maxLength", json.dumps(esquema))
        self.assertIn('"minimum"', json.dumps(esquema))

    def test_b7_openai_solo_con_su_host(self):
        sdk, _ = sdk_falso()
        for url in ("https://evil.example/v1", "https://api.openai.com.evil.example/v1",
                    "https://openrouter.ai/api/v1"):
            with self.subTest(url=url), patch.dict(sys.modules, {"openai": sdk}), \
                    patch.object(Path, "read_text", return_value="llave") as leer, \
                    self.assertRaises(FallaGenerador) as fallo:
                ClienteGeneradorOpenAI(ConfiguracionLlm(perfil="openai", url=url))
            self.assertEqual(fallo.exception.codigo, "config_insegura")
            leer.assert_not_called()

    def test_a8_destino_y_llave_acotados(self):
        sdk, _ = sdk_falso()
        malos = [ConfiguracionLlm(perfil="openai", url="http://api.openai.com/v1"),
                 ConfiguracionLlm(perfil="openai", archivo_clave=Path("/tmp/llave-falsa")),
                 ConfiguracionLlm(perfil="openai", archivo_clave=Path("keys/../.env")),
                 ConfiguracionLlm(perfil="local", url="http://servidor.remoto/v1"),
                 ConfiguracionLlm(perfil="local", url="http://127.0.0.1.evil.com/v1")]
        for config in malos:
            with self.subTest(url=config.url, clave=config.archivo_clave), \
                    patch.dict(sys.modules, {"openai": sdk}), \
                    patch.object(Path, "read_text", return_value="llave") as leer, \
                    self.assertRaises(FallaGenerador) as fallo:
                ClienteGeneradorOpenAI(config)
            self.assertEqual(fallo.exception.codigo, "config_insegura")
            leer.assert_not_called()
        buenos = [ConfiguracionLlm(perfil="openai"), ConfiguracionLlm(),
                  ConfiguracionLlm(url="http://localhost:8080/v1"),
                  ConfiguracionLlm(url="http://127.0.0.1:8080/v1")]
        for config in buenos:
            with self.subTest(url=config.url), patch.dict(sys.modules, {"openai": sdk}), \
                    patch.object(Path, "read_text", return_value="llave"):
                ClienteGeneradorOpenAI(config).cerrar()

    def test_a8_url_invalida_en_la_configuracion(self):
        with patch.dict(os.environ, {"LICIGT_LLM_URL": "ftp://x"}, clear=True):
            obtener_configuracion_llm.cache_clear()
            with self.assertRaises(ValidationError):
                obtener_configuracion_llm()

    def test_fallas_controladas_sin_texto_remoto(self):
        for error, codigo in [(ErrorTiempo("secreto remoto"), "tiempo_agotado"),
                              (ErrorConexion("secreto remoto"), "servicio_no_disponible"),
                              (ErrorApi("secreto remoto"), "api")]:
            sdk, crear = sdk_falso()
            crear.side_effect = error
            with self.subTest(codigo=codigo), patch.dict(sys.modules, {"openai": sdk}):
                c = ClienteGeneradorOpenAI(ConfiguracionLlm())
                with self.assertRaises(FallaGenerador) as fallo:
                    c.generar([], {})
                self.assertEqual(str(fallo.exception), codigo)
        with patch.dict(sys.modules, {"openai": None}), self.assertRaises(FallaGenerador) as fallo:
            ClienteGeneradorOpenAI(ConfiguracionLlm())
        self.assertEqual(fallo.exception.codigo, "sdk_no_disponible")
        for error in (FileNotFoundError(), UnicodeError(), None):
            sdk, _ = sdk_falso()
            with patch.dict(sys.modules, {"openai": sdk}), \
                    patch.object(Path, "read_text", side_effect=error, return_value="  "), \
                    self.assertRaises(FallaGenerador) as fallo:
                ClienteGeneradorOpenAI(ConfiguracionLlm(perfil="openai"))
            self.assertEqual(fallo.exception.codigo, "clave_no_disponible")

    def test_respuesta_vacia_y_rechazo(self):
        for contenido in (None, "", "  "):
            sdk, crear = sdk_falso()
            crear.return_value.choices[0].message.content = contenido
            with patch.dict(sys.modules, {"openai": sdk}), self.assertRaises(FallaGenerador) as fallo:
                ClienteGeneradorOpenAI(ConfiguracionLlm()).generar([], {})
            self.assertEqual(fallo.exception.codigo, "respuesta_vacia")
