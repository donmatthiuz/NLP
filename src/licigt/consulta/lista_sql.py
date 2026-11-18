"""Lista de verificación en Postgres: implementa RepositorioLista con seguridad por fila y atómica por ítem."""

import json
from contextlib import contextmanager

from .lectura import FragmentoRecuperado
from .lista import CambioLista, ItemLista

COLUMNAS_ITEM = ("item_id", "evento_id", "tipo", "categoria", "caracter", "descripcion", "fuentes",
                 "requiere_revision", "motivo_revision", "estado", "creado_por", "creado_en",
                 "actualizado_por", "actualizado_en")
_LISTA = ", ".join(COLUMNAS_ITEM)
_COLUMNAS_CAMBIO = ("item_id", "accion", "estado_anterior", "estado_nuevo", "usuario", "momento")

_ITEMS = f"SELECT {_LISTA} FROM lista_items WHERE tenant_id = %s AND evento_id = %s ORDER BY orden"
_OBTENER = f"SELECT {_LISTA} FROM lista_items WHERE tenant_id = %s AND item_id = %s"
_INSERTAR_ITEM = (f"INSERT INTO lista_items (tenant_id, {_LISTA}) VALUES (%s, {', '.join('%s::jsonb' if c == 'fuentes' else '%s' for c in COLUMNAS_ITEM)})")
_INSERTAR_CAMBIO = ("INSERT INTO lista_cambios (tenant_id, evento_id, item_id, accion, estado_anterior, estado_nuevo, "
                    "usuario, momento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
_ACTUALIZAR = ("UPDATE lista_items SET estado = %s, actualizado_por = %s, actualizado_en = %s "
               f"WHERE tenant_id = %s AND item_id = %s AND estado = %s RETURNING {_LISTA}")
_CAMBIOS = ("SELECT c.item_id, c.accion, c.estado_anterior, c.estado_nuevo, c.usuario, c.momento FROM lista_cambios c "
            "WHERE c.tenant_id = %s AND c.evento_id = %s ORDER BY c.cambio_id")
_FRAGMENTOS = ("SELECT chunk_id, doc_id, tipo_documento, version_ingesta, pagina_inicio, pagina_fin, seccion, texto, "
               "url_origen, meta->>'identificador_version_oficial' FROM fragmentos "
               "WHERE tenant_id = %s AND evento_id = %s AND chunk_id = ANY(%s)")
_CAMPOS_FRAGMENTO = ("chunk_id", "doc_id", "tipo_documento", "version_ingesta", "pagina_inicio", "pagina_fin",
                     "seccion", "texto", "url_origen", "identificador_version_oficial")


@contextmanager
def _transaccion(conn_factory, tenant_id):
    """Una transacción con la empresa fijada para la seguridad por fila, como busqueda._sesion."""
    with conn_factory() as conn, conn.transaction():
        conn.execute("SET LOCAL ROLE licigt_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
        yield conn


def _item(fila) -> ItemLista:
    return ItemLista.model_validate(dict(zip(COLUMNAS_ITEM, fila)))


class RepositorioPostgres:
    """Cumple RepositorioLista; conn_factory devuelve una conexión psycopg con autocommit."""

    def __init__(self, conn_factory):
        self._conn_factory = conn_factory

    def items(self, tenant_id, evento_id):
        with _transaccion(self._conn_factory, tenant_id) as conn:
            return [_item(f) for f in conn.execute(_ITEMS, (tenant_id, evento_id)).fetchall()]

    def obtener(self, tenant_id, item_id):
        with _transaccion(self._conn_factory, tenant_id) as conn:
            fila = conn.execute(_OBTENER, (tenant_id, item_id)).fetchone()
        return _item(fila) if fila else None

    def insertar(self, tenant_id, items, cambios):
        eventos = {i.item_id: i.evento_id for i in items}
        try:
            with _transaccion(self._conn_factory, tenant_id) as conn:
                for i in items:
                    valores = i.model_dump(mode="json")
                    valores["fuentes"] = json.dumps(valores["fuentes"])
                    valores["creado_en"], valores["actualizado_en"] = i.creado_en, i.actualizado_en
                    conn.execute(_INSERTAR_ITEM, (tenant_id, *(valores[c] for c in COLUMNAS_ITEM)))
                for c in cambios:
                    conn.execute(_INSERTAR_CAMBIO, (tenant_id, eventos[c.item_id], *(getattr(c, k) for k in _COLUMNAS_CAMBIO)))
        except Exception as e:
            if getattr(e, "sqlstate", None) == "23505":  # unique_violation
                raise ValueError("item_id repetido")
            raise

    def actualizar_estado(self, tenant_id, item_id, estado_anterior, estado_nuevo, usuario, momento):
        with _transaccion(self._conn_factory, tenant_id) as conn:
            fila = conn.execute(_ACTUALIZAR, (estado_nuevo, usuario, momento, tenant_id, item_id,
                                              estado_anterior)).fetchone()
            if fila is None:
                return None
            nuevo = _item(fila)
            conn.execute(_INSERTAR_CAMBIO, (tenant_id, nuevo.evento_id, item_id, "estado", estado_anterior,
                                            estado_nuevo, usuario, momento))
        return nuevo

    def cambios(self, tenant_id, evento_id):
        with _transaccion(self._conn_factory, tenant_id) as conn:
            return [CambioLista(**dict(zip(_COLUMNAS_CAMBIO, f)))
                    for f in conn.execute(_CAMBIOS, (tenant_id, evento_id)).fetchall()]


class LectorFragmentosPostgres:
    """Adaptador temporal hasta que el rol 2 entregue obtener_fragmentos (aviso del 17 de noviembre); solo SELECT."""

    def __init__(self, conn_factory):
        self._conn_factory = conn_factory

    def obtener(self, ctx, evento_id, chunk_ids):
        if not chunk_ids:
            return {}
        with _transaccion(self._conn_factory, ctx.tenant_id) as conn:
            filas = conn.execute(_FRAGMENTOS, (ctx.tenant_id, evento_id, list(chunk_ids))).fetchall()
        fragmentos = (FragmentoRecuperado(**dict(zip(_CAMPOS_FRAGMENTO, f)), score=0.0) for f in filas)
        return {f.chunk_id: f for f in fragmentos}
