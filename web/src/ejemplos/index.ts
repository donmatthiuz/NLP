import type { RespuestaEstructurada } from '../tipos'
import abstencion from './abstencion.json'
import aclaracion from './aclaracion.json'
import cobertura_parcial from './cobertura_parcial.json'
import comparacion from './comparacion.json'
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
