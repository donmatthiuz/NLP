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

export function esHttps(url: string): boolean {
  try {
    return url.startsWith('https://') && new URL(url).protocol === 'https:'
  } catch {
    return false
  }
}
