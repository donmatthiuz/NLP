"""Escritura de la lista con confirmación explícita; el modelo no tiene ninguna ruta hasta aquí."""

import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .lectura import FragmentoRecuperado, fuente_desde_fragmento
from .lista import CambioLista, Estado, ItemLista, ItemPropuesto, caracter_de_seccion, huella
from .validacion import _original, normalizar_cita

CODIGOS = ("sin_contexto", "sin_items", "cita_no_valida", "item_no_encontrado", "estado_desactualizado")
# El mismo mínimo que el validador de F4 exige a toda cita.
LARGO_MINIMO_CITA = 10


class Confirmacion(BaseModel):
    """Solo la construye la capa que recibe la petición del usuario."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    confirmado: Literal[True]

    @field_validator("confirmado", mode="before")
    @classmethod
    def solo_true(cls, valor):
        # Literal[True] deja pasar 1, que es igual a True en Python.
        if valor is not True:
            raise ValueError("La confirmación debe ser true")
        return valor


class FallaLista(Exception):
    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo


@runtime_checkable
class RepositorioLista(Protocol):
    """Recibe siempre el tenant_id como argumento; nunca lo deduce de un ítem."""

    def items(self, tenant_id: str, evento_id: str) -> list[ItemLista]: ...

    def obtener(self, tenant_id: str, item_id: str) -> ItemLista | None: ...

    def insertar(self, tenant_id: str, items: list[ItemLista], cambios: list[CambioLista]) -> None:
        """Atómica: o entran todos los ítems y sus cambios, o ninguno."""

    def actualizar_estado(self, tenant_id: str, item_id: str, estado_anterior: Estado, estado_nuevo: Estado,
                          usuario: str, momento: datetime) -> ItemLista | None:
        """None si el ítem no existe para esa empresa o si estado_anterior no coincide."""

    def cambios(self, tenant_id: str, evento_id: str) -> list[CambioLista]: ...


class LectorFragmentos(Protocol):
    """Lectura por chunk_id dentro del evento; el rol 2 aún no la entrega."""

    def obtener(self, ctx, evento_id: str, chunk_ids: list[str]) -> dict[str, FragmentoRecuperado]: ...


class RepositorioMemoria:
    """Cumple RepositorioLista con diccionarios por empresa; sirve para pruebas y para la demo."""

    def __init__(self):
        self._items: dict[str, dict[str, ItemLista]] = {}
        self._cambios: dict[str, list[CambioLista]] = {}

    def items(self, tenant_id, evento_id):
        return [i for i in self._items.get(tenant_id, {}).values() if i.evento_id == evento_id]

    def obtener(self, tenant_id, item_id):
        return self._items.get(tenant_id, {}).get(item_id)

    def insertar(self, tenant_id, items, cambios):
        propios = self._items.setdefault(tenant_id, {})
        if any(i.item_id in propios for i in items):
            raise ValueError("item_id repetido")
        propios.update({i.item_id: i for i in items})
        self._cambios.setdefault(tenant_id, []).extend(cambios)

    def actualizar_estado(self, tenant_id, item_id, estado_anterior, estado_nuevo, usuario, momento):
        item = self.obtener(tenant_id, item_id)
        if item is None or item.estado != estado_anterior:
            return None
        nuevo = item.model_copy(update={"estado": estado_nuevo, "actualizado_por": usuario,
                                        "actualizado_en": momento})
        self._items[tenant_id][item_id] = nuevo
        self._cambios[tenant_id].append(CambioLista(
            item_id=item_id, accion="estado", estado_anterior=estado_anterior, estado_nuevo=estado_nuevo,
            usuario=usuario, momento=momento))
        return nuevo

    def cambios(self, tenant_id, evento_id):
        del_evento = {i.item_id for i in self.items(tenant_id, evento_id)}
        return [c for c in self._cambios.get(tenant_id, []) if c.item_id in del_evento]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _sesion(ctx) -> tuple[str, str]:
    """tenant_id y usuario salen solo del contexto autenticado."""
    try:
        tenant_id, usuario = ctx.tenant_id, ctx.usuario
    except Exception:
        raise FallaLista("sin_contexto")
    if not all(isinstance(v, str) and v.strip() for v in (tenant_id, usuario)):
        raise FallaLista("sin_contexto")
    return tenant_id, usuario


def _registrar(auditar, momento, usuario, tenant_id, evento_id, accion, item_ids, error):
    """Sin citas ni texto de fragmentos; si el registro falla, la operación no cambia."""
    try:
        auditar({"momento": momento.isoformat(), "usuario": usuario, "tenant_id": tenant_id,
                 "evento_id": evento_id, "accion": accion, "item_ids": item_ids, "error": error})
    except Exception:
        pass


def _fuente_vigente(item: ItemPropuesto, fragmento: FragmentoRecuperado | None) -> bool:
    """La fuente coincide con el fragmento del evento y su cita sigue siendo un tramo literal del texto."""
    fuente = item.fuentes[0]
    if fragmento is None or fuente_desde_fragmento(fragmento, fuente.cita) != fuente:
        return False
    literal = normalizar_cita(fuente.cita)
    if len(literal) < LARGO_MINIMO_CITA or sum(c.isalnum() for c in literal) < LARGO_MINIMO_CITA:
        return False
    # La misma comprobación del validador de F4: el tramo normalizado está en el texto, sin partir palabras ni números.
    publicado = _original(fragmento.texto, literal, True)
    if publicado != unicodedata.normalize("NFC", " ".join(fuente.cita.split())):
        return False
    esperado = caracter_de_seccion(fragmento.seccion) if item.tipo == "requisito" else "no_indicado"
    return item.caracter == esperado


def guardar_items(ctx, evento_id, items, confirmacion, *, repositorio, lector, auditar=lambda evento: None,
                  reloj=_ahora) -> list[ItemLista]:
    """Guarda como pendientes los ítems cuyas citas siguen siendo válidas; si uno falla no entra ninguno."""
    if not isinstance(confirmacion, Confirmacion):
        raise TypeError("Se requiere la confirmación explícita del usuario")
    momento = reloj()
    try:
        tenant_id, usuario = _sesion(ctx)
    except FallaLista:
        _registrar(auditar, momento, None, None, evento_id, "lista_alta", [], "sin_contexto")
        raise
    try:
        if not items:
            raise FallaLista("sin_items")
        try:
            # Se vuelve a validar el modelo: un ítem armado sin validar no entra.
            propuestos = [ItemPropuesto.model_validate(i.model_dump()) for i in items]
        except (ValidationError, AttributeError):
            raise FallaLista("cita_no_valida")
        chunk_ids = list(dict.fromkeys(i.fuentes[0].chunk_id for i in propuestos))
        try:
            fragmentos = lector.obtener(ctx, evento_id, chunk_ids)
        except Exception:
            raise FallaLista("cita_no_valida")
        if not all(_fuente_vigente(i, fragmentos.get(i.fuentes[0].chunk_id)) for i in propuestos):
            raise FallaLista("cita_no_valida")

        existentes = {huella(evento_id, i): i for i in repositorio.items(tenant_id, evento_id)}
        nuevos, cambios, resultado = [], [], []
        for propuesto in propuestos:
            clave = huella(evento_id, propuesto)
            if clave not in existentes:
                item = ItemLista(**propuesto.model_dump(), item_id=uuid.uuid4().hex, evento_id=evento_id,
                                 estado="pendiente", creado_por=usuario, creado_en=momento,
                                 actualizado_por=usuario, actualizado_en=momento)
                existentes[clave] = item
                nuevos.append(item)
                cambios.append(CambioLista(item_id=item.item_id, accion="alta", estado_anterior=None,
                                           estado_nuevo="pendiente", usuario=usuario, momento=momento))
            resultado.append(existentes[clave])
        if nuevos:
            repositorio.insertar(tenant_id, nuevos, cambios)
    except FallaLista as falla:
        _registrar(auditar, momento, usuario, tenant_id, evento_id, "lista_alta", [], falla.codigo)
        raise
    _registrar(auditar, momento, usuario, tenant_id, evento_id, "lista_alta", [i.item_id for i in nuevos], None)
    return resultado


def cambiar_estado(ctx, item_id, estado_anterior, estado_nuevo, confirmacion, *, repositorio,
                   auditar=lambda evento: None, reloj=_ahora) -> ItemLista:
    """Cambia el estado solo si el ítem sigue en estado_anterior, para no pisar el cambio de otra persona."""
    if not isinstance(confirmacion, Confirmacion):
        raise TypeError("Se requiere la confirmación explícita del usuario")
    momento = reloj()
    try:
        tenant_id, usuario = _sesion(ctx)
    except FallaLista:
        _registrar(auditar, momento, None, None, None, "lista_estado", [item_id], "sin_contexto")
        raise
    evento_id = None
    try:
        actual = repositorio.obtener(tenant_id, item_id)
        if actual is None:
            raise FallaLista("item_no_encontrado")
        evento_id = actual.evento_id
        if actual.estado != estado_anterior:
            raise FallaLista("estado_desactualizado")
        if estado_nuevo == estado_anterior:
            return actual
        nuevo = repositorio.actualizar_estado(tenant_id, item_id, estado_anterior, estado_nuevo, usuario, momento)
        if nuevo is None:
            raise FallaLista("estado_desactualizado")
    except FallaLista as falla:
        _registrar(auditar, momento, usuario, tenant_id, evento_id, "lista_estado", [item_id], falla.codigo)
        raise
    _registrar(auditar, momento, usuario, tenant_id, evento_id, "lista_estado", [item_id], None)
    return nuevo


def listar(ctx, evento_id, *, repositorio) -> list[ItemLista]:
    """Solo lectura, de la empresa del contexto."""
    tenant_id, _ = _sesion(ctx)
    return repositorio.items(tenant_id, evento_id)
