"""Límites independientes de herramientas, regeneraciones y tiempo por solicitud."""

import math
import time


class LimiteAgotado(Exception):
    def __init__(self, tipo):
        self.tipo = tipo
        super().__init__(tipo)


class Presupuesto:
    def __init__(self, max_llamadas=3, max_regeneraciones=1, max_segundos=None, reloj=time.monotonic):
        if any(type(n) is not int or n < 0 for n in (max_llamadas, max_regeneraciones)):
            raise ValueError("Los límites deben ser enteros no negativos")
        if max_segundos is not None and not (math.isfinite(max_segundos) and max_segundos > 0):
            raise ValueError("El límite de tiempo debe ser positivo")
        self.max_segundos, self.reloj, self.inicio = max_segundos, reloj, reloj()
        self.max_llamadas, self.max_regeneraciones = max_llamadas, max_regeneraciones
        self.llamadas = self.regeneraciones = 0

    def usar_llamada(self):
        if self.llamadas >= self.max_llamadas:
            raise LimiteAgotado("llamadas")
        self.llamadas += 1

    def usar_regeneracion(self):
        if self.regeneraciones >= self.max_regeneraciones:
            raise LimiteAgotado("regeneraciones")
        self.regeneraciones += 1

    def cabe_generacion(self, estimada):
        """True si el tiempo gastado más una generación estimada no supera el límite (sin límite, siempre)."""
        return self.max_segundos is None or self.reloj() - self.inicio + estimada <= self.max_segundos
