import type { EstadoItem, ItemLista, ItemPropuesto } from './tipos'

export const ROTULOS_ESTADO_ITEM: Record<EstadoItem, string> = {
  pendiente: 'Pendiente',
  preparado: 'Preparado',
  revisado: 'Revisado',
}
export const ESTADOS_ITEM: EstadoItem[] = ['pendiente', 'preparado', 'revisado']

// Una fila es un ítem propuesto (itemId nulo) o guardado; estado es lo que se ve y estadoGuardado lo que tiene el servidor.
export interface FilaLista {
  clave: string
  item: ItemPropuesto
  itemId: string | null
  estado: EstadoItem
  estadoGuardado: EstadoItem | null
  incluir: boolean
}

export type AccionLista =
  | { tipo: 'cargar'; items: ItemLista[] }
  | { tipo: 'proponer'; items: ItemPropuesto[] }
  | { tipo: 'alternarIncluir'; clave: string }
  | { tipo: 'marcar'; clave: string; estado: EstadoItem }
  | { tipo: 'descartarCambio'; clave: string }
  | { tipo: 'guardadas'; items: ItemLista[] }
  | { tipo: 'cambioGuardado'; item: ItemLista }

// Misma huella que el servidor: fragmento y descripción del ítem.
export const claveDe = (i: ItemPropuesto) => `${i.fuentes[0].chunk_id}|${i.descripcion}`

const filaGuardada = (i: ItemLista): FilaLista => ({
  clave: claveDe(i), item: i, itemId: i.item_id, estado: i.estado, estadoGuardado: i.estado, incluir: false,
})

export const sinGuardar = (f: FilaLista) => f.estadoGuardado !== null && f.estado !== f.estadoGuardado
export const cambiosPendientes = (filas: FilaLista[]) => filas.filter(sinGuardar)
export const itemsAGuardar = (filas: FilaLista[]) => filas.filter((f) => f.itemId === null && f.incluir).map((f) => f.item)

export function reducirLista(filas: FilaLista[], a: AccionLista): FilaLista[] {
  switch (a.tipo) {
    case 'cargar':
      return a.items.map(filaGuardada)
    case 'proponer': {
      const guardadas = filas.filter((f) => f.itemId !== null)
      const claves = new Set(guardadas.map((f) => f.clave))
      const nuevas = a.items.filter((i) => !claves.has(claveDe(i)))
        .map((item): FilaLista => ({ clave: claveDe(item), item, itemId: null, estado: 'pendiente', estadoGuardado: null, incluir: true }))
      return [...guardadas, ...nuevas]
    }
    case 'alternarIncluir':
      return filas.map((f) => (f.clave === a.clave && f.itemId === null ? { ...f, incluir: !f.incluir } : f))
    case 'marcar':
      return filas.map((f) => (f.clave === a.clave && f.itemId !== null ? { ...f, estado: a.estado } : f))
    case 'descartarCambio':
      return filas.map((f) => (f.clave === a.clave && f.estadoGuardado !== null ? { ...f, estado: f.estadoGuardado } : f))
    case 'guardadas': {
      const guardadas = new Map(a.items.map((i) => [claveDe(i), i]))
      const presentes = new Set(filas.map((f) => f.clave))
      const actualizadas = filas.map((f) => {
        const i = guardadas.get(f.clave)
        return i && f.itemId === null ? filaGuardada(i) : f
      })
      return [...actualizadas, ...a.items.filter((i) => !presentes.has(claveDe(i))).map(filaGuardada)]
    }
    case 'cambioGuardado':
      return filas.map((f) => (f.itemId === a.item.item_id ? filaGuardada(a.item) : f))
  }
}

// Una cita de tabla llega como `título | texto`; en pantalla la barra se lee como ": " (o un espacio tras un punto), sin cambiar la cita guardada.
export const mostrarCita = (cita: string) => cita.replace(/(?<=(\S)) \| (?=\S)/g, (_, previo: string) => ('.:;?!'.includes(previo) ? ' ' : ': '))

// La etiqueta de la actividad (lo que precede a la cita en la descripción) va fuera de la cita; la cita es la de la fuente.
export function partesItem(i: ItemPropuesto): { etiqueta: string | null; cita: string } {
  const cita = i.fuentes[0].cita
  if (i.descripcion === cita || !i.descripcion.endsWith(cita)) return { etiqueta: null, cita }
  const etiqueta = i.descripcion.slice(0, -cita.length).replace(/[:\s]+$/, '')
  return { etiqueta: etiqueta || null, cita }
}
