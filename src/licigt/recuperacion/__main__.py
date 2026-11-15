"""CLI de desarrollo: python -m licigt.recuperacion {importar|buscar|comparar} ..."""

import argparse
import json

from .busqueda import Contexto, buscar, comparar_versiones
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
    fila = conn.execute("SELECT evento_id FROM documentos WHERE tenant_id = %s AND %s IN (evento_id, numero_evento)",
                        (a.tenant_id, a.evento)).fetchone()
    if not fila:
        raise SystemExit(f"Evento no encontrado para la empresa: {a.evento}")
    ctx = Contexto(a.tenant_id)
    out = (buscar(ctx, fila[0], a.pregunta, a.variante, conn=conn) if a.cmd == "buscar"
           else comparar_versiones(ctx, fila[0], a.pregunta, conn=conn))
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
