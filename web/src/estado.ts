import type { Estado, Fuente, RespuestaEstructurada } from './tipos'

type Decisivos = Pick<RespuestaEstructurada, 'needs_clarification' | 'abstained' | 'needs_human_review'>

// Precedencia: aclaración, abstención, revisión humana y respuesta.
export function estadoDe(r: Decisivos): Estado {
  if (r.needs_clarification) return 'aclaracion'
  if (r.abstained) return 'abstencion'
  if (r.needs_human_review) return 'revision'
  return 'respuesta'
}

export const ROTULOS: Record<Estado, string> = {
  respuesta: 'Respuesta',
  abstencion: 'Sin información suficiente',
  revision: 'Requiere revisión humana',
  aclaracion: 'Se necesita una aclaración',
}

// Un grupo por doc_id, en el orden de la primera aparición.
export function agruparPorDocumento(fuentes: Fuente[]): { doc_id: string; fuentes: Fuente[] }[] {
  const grupos = new Map<string, Fuente[]>()
  for (const f of fuentes) grupos.set(f.doc_id, [...(grupos.get(f.doc_id) ?? []), f])
  return [...grupos].map(([doc_id, fs]) => ({ doc_id, fuentes: fs }))
}

// Banda de revisión: nombra el motivo; "las fuentes difieren" solo con fuentes de dos documentos o más.
export function motivoRevision(r: Pick<RespuestaEstructurada, 'needs_human_review' | 'sources'>): string | null {
  if (!r.needs_human_review) return null
  const comun = 'El sistema no decide cuál está vigente; revise los documentos originales.'
  const documentos = new Set(r.sources.map((f) => f.doc_id)).size
  if (documentos === 0) return 'El sistema marcó esta consulta para revisión humana; revise los documentos originales.'
  return documentos >= 2
    ? `Las fuentes difieren o un dato crítico es ambiguo. ${comun}`
    : `Un dato crítico es ambiguo o puede estar desactualizado. ${comun}`
}

export function esHttps(url: string): boolean {
  try {
    return url.startsWith('https://') && new URL(url).protocol === 'https:'
  } catch {
    return false
  }
}

// El backend no guarda memoria entre preguntas: ante una aclaración la caja
// conserva la pregunta original, con el cursor al final, para completarla.
export function alAclarar(pregunta: string): { texto: string; cursor: number } {
  return { texto: pregunta, cursor: pregunta.length }
}

export const MENSAJE_SESION_TERMINADA = 'La sesión terminó. Inicie sesión de nuevo.'

// Un solo texto para usuario, empresa y rol en la cabecera.
export const textoSesion = (s: { usuario: string; tenant_id: string; rol: string }) =>
  `${s.usuario} · ${s.tenant_id} · rol ${s.rol}`
