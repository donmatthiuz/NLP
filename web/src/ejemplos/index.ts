import type { DocumentosEvento, PropuestaLista, RespuestaEstructurada } from '../tipos'
import abstencion from './abstencion.json'
import aclaracion from './aclaracion.json'
import cobertura_parcial from './cobertura_parcial.json'
import comparacion from './comparacion.json'
import lista from './lista.json'
import respuesta from './respuesta.json'

export interface Ejemplo {
  id: string
  titulo: string
  pregunta: string
  respuesta: RespuestaEstructurada
}

// Respuestas con datos reales del evento 222-IGSS-2023 (empresa_demo.zip).
export const EJEMPLOS: Ejemplo[] = [
  { id: 'respuesta', titulo: 'Respuesta con fuentes', pregunta: '¿Cuál es el monto del seguro de caución de cumplimiento?', respuesta },
  { id: 'abstencion', titulo: 'Abstención', pregunta: '¿Cuál es el precio unitario máximo por vial?', respuesta: abstencion },
  { id: 'comparacion', titulo: 'Comparación con revisión humana', pregunta: 'Compare la fecha de recepción de ofertas entre las bases y la modificación 1', respuesta: comparacion },
  { id: 'aclaracion', titulo: 'Aclaración', pregunta: '¿Cuál es la fecha?', respuesta: aclaracion },
  { id: 'cobertura_parcial', titulo: 'Cobertura parcial', pregunta: '¿Se puede prorrogar el plazo para adjudicar?', respuesta: cobertura_parcial },
] as Ejemplo[]

// Propuesta de lista con datos reales del 222: dos requisitos y las dos fechas de recepción de ofertas que difieren.
export const EJEMPLO_PROPUESTA = lista as PropuestaLista

// Documentos del evento 222-IGSS-2023 tal como los inventarió el rol 2: la modificación trae una página sin indexar y un anexo ausente.
export const EJEMPLO_DOCUMENTOS: DocumentosEvento = {
  evento_id: '222-IGSS-2023',
  documentos: [
    {
      doc_id: '03791a3471c04c0f9cc260814564756e', tipo_documento: 'bases', version_oficial: null, version_ingesta: 1,
      estado: 'completo', paginas_total: 35, paginas_no_indexadas: [], advertencias: [],
    },
    {
      doc_id: 'd41480e5b0ce4c16bf18f66225ada2dc', tipo_documento: 'modificacion', version_oficial: 'Modificación Número 1',
      version_ingesta: 1, estado: 'requiere_revision', paginas_total: 4, paginas_no_indexadas: [4],
      advertencias: ['Hay páginas incompletas o ilegibles', 'Menciona un anexo de 11 hojas que no está cargado'],
    },
  ],
}
