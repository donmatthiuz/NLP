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

// Solo las advertencias del documento: las páginas sin indexar y el estado ya van en la línea de resumen de la tarjeta.
export const advertenciasDe = (d: DocumentoEvento): string[] => d.advertencias

// doc_id a tipo legible, para rotular las citas con el tipo antes del hash.
export type MapaTipos = Record<string, string>
export const mapaTipos = (documentos: DocumentoEvento[]): MapaTipos =>
  Object.fromEntries(documentos.map((d) => [d.doc_id, rotuloTipoDocumento(d.tipo_documento)]))

// Sin el documento en el mapa (modo ejemplo o falla de carga) queda solo el hash.
export const rotuloDocumento = (docId: string, tipos?: MapaTipos) => (tipos?.[docId] ? `${tipos[docId]} · ${docId}` : docId)

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
