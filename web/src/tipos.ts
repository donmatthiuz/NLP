// Copia a mano de Fuente y RespuestaEstructurada: src/licigt/consulta/esquemas.py
export interface Fuente {
  doc_id: string
  source: string
  page: number
  page_end: number | null
  chunk_id: string
  version_ingesta: number
  version_oficial: string | null
  cita: string
}

export type NombreHerramienta = 'buscar_documentos' | 'extraer_requisitos' | 'comparar_versiones'

export interface RespuestaEstructurada {
  answer: string
  sources: Fuente[]
  abstained: boolean
  tool_used: NombreHerramienta | null
  needs_human_review: boolean
  evento_id: string
  coverage_status: 'parcial' | 'sin_faltantes_detectados'
  warnings: string[]
  needs_clarification: boolean
  clarification_question: string | null
}

export type Estado = 'respuesta' | 'abstencion' | 'revision' | 'aclaracion'
