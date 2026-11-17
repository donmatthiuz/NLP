"""Consultas de requisitos y fechas literales; lógica pura, sin servicios."""

import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .entrada import normalizar
from .esquemas import Categoria, Entero, TextoNoVacio
from .jev import Probabilidad

CONSULTAS_POR_CATEGORIA: dict[Categoria, str] = {
    "administrativa": "requisitos administrativos y documentos que debe contener la plica",
    "legal": "requisitos legales, constancias, declaraciones juradas y solvencias",
    "tecnica": "especificaciones técnicas del medicamento, presentación y concentración",
    "financiera": "requisitos financieros, garantías, fianzas y estados financieros",
}
CONSULTA_CRONOGRAMA = "cronograma de actividades, fechas y plazos del evento"

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}
PATRON_FECHA = re.compile(
    r"\b([0-9]{1,2})\s+de\s+(" + "|".join(MESES) + r")\s+del?\s+([0-9]{4})\b")
ABREVIATURAS = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
                "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
NOMBRE_MES = {numero: mes for mes, numero in reversed(MESES.items())}
# Sobre texto normalizado; una abreviatura cuenta junto a un día, con punto o ante un año, para no tomar "mar" por un mes.
_NOMBRES = "|".join(sorted([*MESES, *ABREVIATURAS], key=len, reverse=True))
PATRON_DIA_MES = re.compile(
    r"\b([0-9]{1,2})(?:\s+(?:de\s+)?|-)(" + _NOMBRES + r")\b\.?(?:(?:\s+(?:del?\s+)?|-)([0-9]{4})\b)?")
# Una abreviatura sin día cuenta si lleva punto o si le sigue un año.
PATRON_ABREVIATURA = re.compile(
    r"\b(" + "|".join(sorted(ABREVIATURAS, key=len, reverse=True))
    + r")(?:\.|(?=\s+(?:del?\s+)?[0-9]{4}\b))")
PATRON_MES = re.compile(r"\b(" + "|".join(MESES) + r")\b")
# Día y mes en el uso de Guatemala; los días en romanos y las cifras con letras quedan fuera.
PATRON_FECHA_NUMERICA = re.compile(r"(?<![0-9])([0-9]{1,2})([/.\-])([0-9]{1,2})\2([0-9]{4})(?![0-9])")


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


def _a_ascii(texto: str) -> str:
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in texto)


def normalizar_cifras(texto: str) -> str:
    """Dígitos Unicode a ASCII y miles sin separador: "Q1 000 000.00" y "Q1,000,000.00" coinciden."""
    texto = re.sub(r"(?<=[0-9])[ \u00a0\u202f\u2009](?=[0-9]{3}(?![0-9]))", "", _a_ascii(texto))
    return re.sub(r"(?<=[0-9]),(?=[0-9]{3}(?![0-9]))", "", texto)


def fechas_numericas_a_texto(texto: str) -> str:
    """Reescribe dd/mm/aaaa, dd-mm-aaaa y dd.mm.aaaa válidos como "d de mes de aaaa"."""
    def reescribir(m):
        dia, mes = int(m[1]), int(m[3])
        if not (1 <= dia <= 31 and 1 <= mes <= 12):
            return m[0]
        return f"{dia} de {NOMBRE_MES[mes]} de {m[4]}"
    return PATRON_FECHA_NUMERICA.sub(reescribir, _a_ascii(texto))


def fechas_en_texto(texto: str) -> tuple[set[tuple[int, int, int]], set[int]]:
    """Fechas completas (año, mes, día) y números de mes mencionados, con o sin día y año."""
    texto = fechas_numericas_a_texto(normalizar(unicodedata.normalize("NFKC", texto)))
    fechas, meses = set(), set()
    for dia, mes, anio in PATRON_DIA_MES.findall(texto):
        numero = MESES.get(mes) or ABREVIATURAS[mes]
        meses.add(numero)
        if anio:
            fechas.add((int(anio), numero, int(dia)))
    meses.update(MESES[m] for m in PATRON_MES.findall(texto))
    meses.update(ABREVIATURAS[m] for m in PATRON_ABREVIATURA.findall(texto))
    return fechas, meses
