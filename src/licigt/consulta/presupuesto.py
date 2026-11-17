"""Límites independientes de herramientas y regeneraciones por solicitud."""


class LimiteAgotado(Exception):
    def __init__(self, tipo):
        self.tipo = tipo
        super().__init__(tipo)


class Presupuesto:
    def __init__(self, max_llamadas=3, max_regeneraciones=1):
        if any(type(n) is not int or n < 0 for n in (max_llamadas, max_regeneraciones)):
            raise ValueError("Los límites deben ser enteros no negativos")
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
