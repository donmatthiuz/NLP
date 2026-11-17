import type { DocumentoEvento } from './tipos'

const TIPOS: Record<string, string> = { bases: 'Bases', modificacion: 'Modificación', aclaracion: 'Aclaración' }
const ESTADOS: Record<string, string> = {
  completo: 'Completo', requiere_revision: 'Requiere revisión', incompleto: 'Incompleto',
}

export const rotuloTipoDocumento = (tipo: string) => TIPOS[tipo] ?? tipo
export const rotuloEstadoDocumento = (estado: string) => ESTADOS[estado] ?? estado

// Lo que falta de un documento: páginas sin indexar, un estado distinto de completo y las advertencias del inventario.
export function faltantesDe(d: DocumentoEvento): string[] {
  const faltantes: string[] = []
  if (d.paginas_no_indexadas.length > 0) faltantes.push(`Páginas sin indexar: ${d.paginas_no_indexadas.join(', ')}`)
  if (d.estado !== 'completo') faltantes.push(`Estado: ${rotuloEstadoDocumento(d.estado).toLowerCase()}`)
  return [...faltantes, ...d.advertencias]
}

export function textoPaginas(d: DocumentoEvento): string {
  if (d.paginas_total === null) return 'Páginas no informadas'
  const paginas = `${d.paginas_total} ${d.paginas_total === 1 ? 'página' : 'páginas'}`
  const sin = d.paginas_no_indexadas
  return sin.length === 0 ? `${paginas}, todas indexadas` : `${paginas}, ${sin.length} sin indexar (p. ${sin.join(', ')})`
}

export function resumenCobertura(documentos: DocumentoEvento[]) {
  const total = documentos.length
  const conFaltantes = documentos.filter((d) => faltantesDe(d).length > 0).length
  if (total === 0) return { total, conFaltantes, texto: 'No hay documentos cargados para este evento' }
  const documentosTxt = `${total} ${total === 1 ? 'documento' : 'documentos'}`
  return { total, conFaltantes, texto: `${documentosTxt}, ${conFaltantes === 0 ? 'sin información faltante' : `${conFaltantes} con información faltante`}` }
}
