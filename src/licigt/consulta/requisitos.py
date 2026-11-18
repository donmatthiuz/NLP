"""Consultas de requisitos y fechas literales; lógica pura, sin servicios."""

import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .esquemas import Categoria, Entero, TextoNoVacio
from .jev import Probabilidad

CONSULTAS_POR_CATEGORIA: dict[Categoria, str] = {
    "administrativa": "requisitos administrativos y documentos que debe contener la plica",
    "legal": "requisitos legales, constancias, declaraciones juradas y solvencias",
    "tecnica": "especificaciones técnicas del medicamento, presentación y concentración",
    "financiera": "requisitos financieros, garantías, fianzas y estados financieros",
}
# Con el cronograma como tabla de descripción (R3), la consulta genérica ya no traía el fragmento 2.2 del evento 222
# entre los 5 primeros; nombrar las actividades de la tabla sí.
CONSULTA_CRONOGRAMA = ("cronograma de actividades: período para adquirir los documentos, inducción, "
                       "aclaraciones, recepción de ofertas y apertura de plicas")

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}
PATRON_FECHA = re.compile(
    r"\b([0-9]{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+del?\s+([0-9]{4})\b")
ABREVIATURAS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
                "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}


class FechaCandidata(BaseModel):
    """Fecha copiada de la evidencia, con los juicios de actividad y respaldo separados."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: TextoNoVacio
    doc_id: TextoNoVacio
    tipo_documento: str
    pagina: Entero = Field(ge=1)
    literal: TextoNoVacio
    fecha: date
    actividad: str | None = None
    estado: Literal["verificada", "no_verificada", "fuera_del_cronograma"] = "no_verificada"
    prob_actividad: Probabilidad | None = None
    prob_respaldo: Probabilidad | None = None


def encontrar_fechas(texto: str) -> list[tuple[str, date, int]]:
    """Normaliza para buscar, conservando literal y posición del texto original."""
    normalizado, posiciones = [], []
    for posicion, caracter in enumerate(texto):
        letras = "".join(c for c in unicodedata.normalize("NFD", caracter.lower())
                         if unicodedata.category(c) != "Mn")
        normalizado.append(letras)
        posiciones.extend([posicion] * len(letras))
    fechas = []
    for coincidencia in PATRON_FECHA.finditer("".join(normalizado)):
        dia, mes, anio = coincidencia.groups()
        try:
            fecha = date(int(anio), MESES[mes], int(dia))
        except ValueError:
            continue
        inicio = posiciones[coincidencia.start()]
        fin = posiciones[coincidencia.end() - 1] + 1
        fechas.append((texto[inicio:fin], fecha, inicio))
    return fechas
