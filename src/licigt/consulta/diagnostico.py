"""Diagnóstico de una consulta real: corre consultar() y muestra cada etapa sin imprimir texto de PDF completo.

Uso: make consultar Q="..." EVENTO=222-IGSS-2023 [VECES=1]. El tenant es el de la demostración (empresa_demo),
como si lo hubiera puesto la sesión; la pregunta nunca lo decide."""

import argparse
import json
import os

from licigt.recuperacion import busqueda
from licigt.recuperacion.busqueda import Contexto, resolver_evento
from licigt.recuperacion.indice import conectar

from . import orquestador
from .enrutador import crear_enrutador
from .llm import ClienteGeneradorOpenAI

RECORTE = 140


def _corto(texto):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= RECORTE else texto[:RECORTE] + "..."


def _cita_modelo(afirmaciones, error):
    """La cita que escribió el modelo en la posición del error, recortada; None si la posición no existe."""
    try:
        cita = afirmaciones[error.afirmacion - 1]["citas"][error.cita - 1]["cita"]
        return _corto(cita) if isinstance(cita, str) else None
    except (TypeError, KeyError, IndexError):
        return None


def _afirmacion_modelo(afirmaciones, error):
    """El texto y los datos que escribió el modelo en la afirmación del error, recortados; None si no existe."""
    try:
        a = afirmaciones[error.afirmacion - 1]
        return {"texto": _corto(a["texto"]), "datos": [_corto(d.get("literal", "")) for d in a.get("datos", [])],
                "citas": [_corto(c.get("cita", "")) for c in a.get("citas", [])]}
    except (TypeError, KeyError, IndexError, AttributeError):
        return None


class _Recuperador:
    """Deja pasar las llamadas y guarda lo que devolvió el rol 2 para mostrarlo."""
    def __init__(self, conn):
        self.conn, self.busquedas = conn, []

    def buscar(self, ctx, evento_id, pregunta, variante="mejorada", k=5, conn=None):
        crudo = busqueda.buscar(ctx, evento_id, pregunta, variante, k, conn=self.conn)
        self.busquedas.append((pregunta, crudo))
        return crudo

    def comparar_versiones(self, ctx, evento_id, pregunta, k=2, conn=None):
        return busqueda.comparar_versiones(ctx, evento_id, pregunta, k, conn=self.conn)


class _Generador:
    def __init__(self):
        self.base, self.salidas = ClienteGeneradorOpenAI(), []
        self.modelo_generador = self.base.modelo_generador

    def generar(self, mensajes, esquema, **kwargs):
        crudo = self.base.generar(mensajes, esquema, **kwargs)
        self.salidas.append(crudo)
        return crudo


def _una_vez(ctx, evento_id, pregunta, conn, numero_evento=None):
    rec, gen, validaciones = _Recuperador(conn), _Generador(), []
    validar_original = orquestador.validar

    def validar_visible(crudo, evidencia, *args, **kwargs):
        resultado = validar_original(crudo, evidencia, *args, **kwargs)
        if isinstance(resultado, list):
            try:
                afirmaciones = json.loads(crudo)["afirmaciones"]
            except Exception:
                afirmaciones = []
            validaciones.append([
                {"codigo": e.codigo, "afirmacion": e.afirmacion, "cita": e.cita,
                 "cita_modelo": _cita_modelo(afirmaciones, e), "afirmacion_modelo": _afirmacion_modelo(afirmaciones, e)}
                for e in resultado])
        else:
            validaciones.append("ok" if not resultado.abstained else "abstener")
        return resultado

    auditoria = []
    orquestador.validar = validar_visible
    try:
        r = orquestador.consultar(ctx, evento_id, pregunta, enrutador=crear_enrutador(), recuperador=rec,
                                  generador=gen, auditar=auditoria.append, numero_evento=numero_evento)
    finally:
        orquestador.validar = validar_original
    return r, rec, gen, validaciones, auditoria[-1] if auditoria else {}


def main():
    pregunta, evento = os.environ.get("DIAG_PREGUNTA", ""), os.environ.get("DIAG_EVENTO", "")
    if not pregunta.strip() or not evento.strip():
        raise SystemExit('Uso: make consultar Q="..." [EVENTO=222-IGSS-2023] [VECES=1]')
    try:
        veces = max(1, min(int(os.environ.get("DIAG_VECES", "1")), 20))
    except ValueError:
        raise SystemExit("VECES debe ser un entero")
    a = argparse.Namespace(pregunta=pregunta, evento=evento, veces=veces)
    conn = conectar()
    ctx = Contexto("empresa_demo", "diagnostico")
    evento_id = resolver_evento(ctx, a.evento, conn)
    if not evento_id:
        raise SystemExit(f"Evento no encontrado para la empresa: {a.evento}")
    for n in range(1, a.veces + 1):
        r, rec, gen, validaciones, aud = _una_vez(ctx, evento_id, a.pregunta, conn, a.evento)
        print(f"--- corrida {n} ---")
        print("herramienta:", r.tool_used, "| intencion:", aud.get("intencion"))
        for consulta, crudo in rec.busquedas:
            print(f"recuperacion ({_corto(consulta)}) suficiente={crudo['suficiente']}")
            for f in crudo["fragmentos"]:
                print(f"  {f['chunk_id']} p.{f['pagina_inicio']} {f['tipo_documento']} score={f['score']:.4f} "
                      f"incluido_por={f.get('incluido_por')} seccion={_corto(f.get('seccion') or '')[:50]}")
            for al in crudo.get("alertas", []):
                print("  alerta:", al["tipo"], al.get("doc_id"), al.get("paginas_no_indexadas"))
        print("generaciones:", len(gen.salidas), "| validaciones:", json.dumps(validaciones, ensure_ascii=False))
        print("validacion:", aud.get("validacion"), "| error:", aud.get("error"), "| latencia_ms:", round(aud.get("latencia_ms", 0)))
        print(f"abstained={r.abstained} needs_human_review={r.needs_human_review} coverage={r.coverage_status} "
              f"warnings={r.warnings}")
        print("fuentes:", [(s.chunk_id, s.pagina) if hasattr(s, "pagina") else s.chunk_id for s in r.sources])
        if not r.abstained:
            print("respuesta:", _corto(r.answer))


if __name__ == "__main__":
    main()
