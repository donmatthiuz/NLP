import type { DocumentosEvento, EstadoItem, ItemLista, ItemPropuesto, PropuestaLista, RespuestaEstructurada } from './tipos'

export interface ResultadoApi {
  respuesta: RespuestaEstructurada
  sinAutenticacion: boolean
}

export class ErrorConsulta extends Error {}

// El cuerpo lleva solo la pregunta: el tenant sale de la sesión del servidor.
export async function consultarApi(eventoId: string, pregunta: string): Promise<ResultadoApi> {
  let res: Response
  try {
    res = await fetch(`/api/eventos/${encodeURIComponent(eventoId)}/consultas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pregunta }),
    })
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
  if (res.status === 422) throw new ErrorConsulta('La pregunta no es válida (422)')
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
  return {
    respuesta: (await res.json()) as RespuestaEstructurada,
    sinAutenticacion: res.headers.get('X-LiciGT-Autenticacion') === 'ninguna-demo',
  }
}

// Solo lectura; sin tenant_id: sale de la sesión del servidor.
export async function documentosApi(eventoId: string): Promise<DocumentosEvento> {
  let res: Response
  try {
    res = await fetch(`/api/eventos/${encodeURIComponent(eventoId)}/documentos`)
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
  return (await res.json()) as DocumentosEvento
}

export const MENSAJE_CONFLICTO = 'Otro usuario cambió este ítem. Recargue la lista antes de guardar.'

const MENSAJES_LISTA: Record<string, string> = {
  estado_desactualizado: MENSAJE_CONFLICTO,
  item_no_encontrado: 'El ítem ya no existe. Recargue la lista.',
  cita_no_valida: 'Una cita ya no coincide con el documento del evento. No se guardó nada; proponga la lista otra vez.',
  sin_items: 'No hay ítems para guardar.',
}

export class ErrorLista extends Error {
  codigo: string
  constructor(mensaje: string, codigo: string) {
    super(mensaje)
    this.codigo = codigo
  }
}

const rutaLista = (eventoId: string) => `/api/eventos/${encodeURIComponent(eventoId)}/lista`

async function pedirLista<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ErrorLista('La API no respondió', 'sin_respuesta')
  }
  if (!res.ok) {
    // Solo el código: el detalle nunca trae texto de documentos.
    let codigo = `http_${res.status}`
    try {
      const cuerpo = await res.json()
      if (typeof cuerpo?.detail?.codigo === 'string') codigo = cuerpo.detail.codigo
    } catch { /* cuerpo no JSON */ }
    throw new ErrorLista(MENSAJES_LISTA[codigo] ?? `La API devolvió un error (${res.status})`, codigo)
  }
  return (await res.json()) as T
}

const enviar = (metodo: string, cuerpo: unknown): RequestInit => ({
  method: metodo, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo),
})

const exigir = (confirmado: unknown) => {
  if (confirmado !== true) throw new ErrorLista('Falta la confirmación del usuario', 'sin_confirmacion')
}

// Ninguna función envía tenant_id: sale de la sesión del servidor.
export const proponerApi = (eventoId: string) =>
  pedirLista<PropuestaLista>(`${rutaLista(eventoId)}/propuesta`, enviar('POST', {}))

export const listarApi = (eventoId: string) => pedirLista<ItemLista[]>(rutaLista(eventoId))

export async function guardarApi(eventoId: string, items: ItemPropuesto[], confirmado: boolean) {
  exigir(confirmado)
  return pedirLista<ItemLista[]>(rutaLista(eventoId), enviar('POST', { items, confirmado: true }))
}

export async function cambiarEstadoApi(
  eventoId: string, itemId: string, anterior: EstadoItem, nuevo: EstadoItem, confirmado: boolean,
) {
  exigir(confirmado)
  return pedirLista<ItemLista>(`${rutaLista(eventoId)}/${encodeURIComponent(itemId)}`,
    enviar('PATCH', { estado_anterior: anterior, estado_nuevo: nuevo, confirmado: true }))
}
