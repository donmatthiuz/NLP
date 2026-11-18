"""CLI de desarrollo: python -m licigt.recuperacion {importar|buscar|comparar} ..."""

import argparse
import json

from .busqueda import Contexto, buscar, comparar_versiones, resolver_evento
from .indice import importar

p = argparse.ArgumentParser(prog="licigt.recuperacion")
sub = p.add_subparsers(dest="cmd", required=True)
sub.add_parser("importar").add_argument("zip", nargs="?", default="entregables/recuperacion/empresa_demo.zip")
for nombre in ("buscar", "comparar"):
    s = sub.add_parser(nombre)
    # shortcut: --tenant-id solo para desarrollo; en la app lo resuelve la sesión autenticada (rol 4).
    s.add_argument("--tenant-id", default="empresa_demo")
    s.add_argument("--evento", required=True, help="evento_id o numero_evento (p. ej. 222-IGSS-2023)")
    s.add_argument("pregunta")
    if nombre == "buscar":
        s.add_argument("--variante", choices=("base", "mejorada"), default="mejorada")
a = p.parse_args()

if a.cmd == "importar":
    print(importar(a.zip))
else:
    from .indice import conectar
    conn = conectar()
    ctx = Contexto(a.tenant_id)
    evento_id = resolver_evento(ctx, a.evento, conn)  # con la sesión de la empresa (RLS)
    if not evento_id:
        raise SystemExit(f"Evento no encontrado para la empresa: {a.evento}")
    out = (buscar(ctx, evento_id, a.pregunta, a.variante, conn=conn) if a.cmd == "buscar"
           else comparar_versiones(ctx, evento_id, a.pregunta, conn=conn))
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
