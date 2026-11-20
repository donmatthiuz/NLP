import { MENSAJE_SESION_TERMINADA } from './estado'
import type { DocumentosEvento, EstadoItem, ItemLista, ItemPropuesto, PropuestaLista, RespuestaEstructurada, Sesion } from './tipos'

export class ErrorConsulta extends Error {}

// La cookie de sesión es HttpOnly: la web nunca la lee ni la guarda; el navegador la envía solo (same-origin).
export class ErrorNoAutenticado extends Error {
  constructor() { super(MENSAJE_SESION_TERMINADA) }
}

export const MENSAJE_CREDENCIALES = 'Usuario o contraseña no válidos'
export const MENSAJE_ROL = 'Su rol no permite modificar la lista'

let avisarSesionPerdida: (() => void) | null = null
export const alPerderSesion = (fn: (() => void) | null) => { avisarSesionPerdida = fn }

// Cualquier 401 de /api a mitad de uso devuelve a la pantalla de inicio de sesión.
function sesionPerdida(res: Response): never | void {
  if (res.status !== 401) return
  avisarSesionPerdida?.()
  throw new ErrorNoAutenticado()
}

export async function obtenerSesionApi(): Promise<Sesion | null> {
  let res: Response
  try {
    res = await fetch('/api/sesion')
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
  if (res.status === 401) return null
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
  return (await res.json()) as Sesion
}

// Solo usuario y contraseña; la contraseña no se guarda en ningún almacenamiento.
export async function iniciarSesionApi(usuario: string, contrasena: string): Promise<void> {
  let res: Response
  try {
    res = await fetch('/api/sesion', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ usuario, contrasena }),
    })
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
  if (res.status === 401 || res.status === 422) throw new ErrorConsulta(MENSAJE_CREDENCIALES)
  if (res.status === 503) throw new ErrorConsulta('El servicio de sesión no está configurado')
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
}

export async function cerrarSesionApi(): Promise<void> {
  try {
    await fetch('/api/sesion', { method: 'DELETE' })
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
}

// El cuerpo lleva solo la pregunta: el tenant sale de la sesión del servidor.
export async function consultarApi(eventoId: string, pregunta: string): Promise<RespuestaEstructurada> {
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
  sesionPerdida(res)
  if (res.status === 422) throw new ErrorConsulta('La pregunta no es válida (422)')
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
  return (await res.json()) as RespuestaEstructurada
}

// Solo lectura; sin tenant_id: sale de la sesión del servidor.
export async function documentosApi(eventoId: string): Promise<DocumentosEvento> {
  let res: Response
  try {
    res = await fetch(`/api/eventos/${encodeURIComponent(eventoId)}/documentos`)
  } catch {
    throw new ErrorConsulta('La API no respondió')
  }
  sesionPerdida(res)
  if (!res.ok) throw new ErrorConsulta(`La API devolvió un error (${res.status})`)
  return (await res.json()) as DocumentosEvento
}

export const rutaOriginal = (eventoId: string, docId: string, pagina: number) =>
  `/api/eventos/${encodeURIComponent(eventoId)}/documentos/${encodeURIComponent(docId)}/original?p=${pagina}#page=${pagina}`

// Enlace externo: solo un PDF directo (la ruta termina en .pdf) abre en la página; si no, no hay fragmento útil.
export function urlExternaConPagina(url: string, pagina: number): string | null {
  try {
    const u = new URL(url)
    if (!u.pathname.toLowerCase().endsWith('.pdf')) return null
    u.hash = `page=${pagina}`
    return u.toString()
  } catch {
    return null
  }
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
  sesionPerdida(res)
  if (res.status === 403) throw new ErrorLista(MENSAJE_ROL, 'rol_no_permitido')
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
