import type { RespuestaEstructurada } from './tipos'

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
