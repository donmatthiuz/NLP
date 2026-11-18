import { EJEMPLO_PROPUESTA } from './ejemplos'
import { ErrorLista, MENSAJE_CONFLICTO } from './api'
import { claveDe } from './lista'
import type { EstadoItem, ItemLista, ItemPropuesto, PropuestaLista } from './tipos'

// Servidor de mentira para el modo ejemplos: vive en memoria y no llama a la API.
// Con ?conflicto=1 el primer cambio de estado responde como si otra persona ya lo hubiera cambiado.
export function crearListaEjemplos(eventoId: string, conflicto = false) {
  const guardados: ItemLista[] = []
  let conflictoPendiente = conflicto
  const ahora = () => new Date().toISOString()
  return {
    async proponer(): Promise<PropuestaLista> {
      return EJEMPLO_PROPUESTA
    },
    async listar(): Promise<ItemLista[]> {
      return [...guardados]
    },
    async guardar(items: ItemPropuesto[]): Promise<ItemLista[]> {
      return items.map((i) => {
        const previo = guardados.find((g) => claveDe(g) === claveDe(i))
        if (previo) return previo
        const nuevo: ItemLista = {
          ...i, item_id: `ejemplo-${guardados.length + 1}`, evento_id: eventoId, estado: 'pendiente',
          creado_por: 'demo', creado_en: ahora(), actualizado_por: 'demo', actualizado_en: ahora(),
        }
        guardados.push(nuevo)
        return nuevo
      })
    },
    async cambiarEstado(itemId: string, anterior: EstadoItem, nuevo: EstadoItem): Promise<ItemLista> {
      const i = guardados.findIndex((g) => g.item_id === itemId)
      if (i < 0) throw new ErrorLista('El ítem ya no existe. Recargue la lista.', 'item_no_encontrado')
      if (conflictoPendiente || guardados[i].estado !== anterior) {
        conflictoPendiente = false
        throw new ErrorLista(MENSAJE_CONFLICTO, 'estado_desactualizado')
      }
      guardados[i] = { ...guardados[i], estado: nuevo, actualizado_en: ahora() }
      return guardados[i]
    },
  }
}
