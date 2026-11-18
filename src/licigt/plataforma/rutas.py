"""Rutas por defecto, relativas a la raíz del repo, y su ajuste por variable de entorno."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]


def ruta(variable: str, por_defecto: str) -> Path:
    valor = os.environ.get(variable)
    return Path(valor) if valor else RAIZ / por_defecto
