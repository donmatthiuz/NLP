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

// Copia a mano de ItemPropuesto, ItemLista y PropuestaLista: src/licigt/consulta/lista.py
export type Categoria = 'administrativa' | 'legal' | 'tecnica' | 'financiera'
export type Caracter = 'fundamental' | 'no_fundamental' | 'no_indicado'
export type EstadoItem = 'pendiente' | 'preparado' | 'revisado'

export interface ItemPropuesto {
  tipo: 'requisito' | 'fecha'
  categoria: Categoria | null
  caracter: Caracter
  descripcion: string
  fuentes: Fuente[]
  requiere_revision: boolean
  motivo_revision: string | null
}

export interface ItemLista extends ItemPropuesto {
  item_id: string
  evento_id: string
  estado: EstadoItem
  creado_por: string
  creado_en: string
  actualizado_por: string
  actualizado_en: string
}

export interface PropuestaLista {
  evento_id: string
  respuesta: RespuestaEstructurada
  items: ItemPropuesto[]
}

// Copia a mano de DocumentoEvento y DocumentosEvento: src/licigt/consulta/api.py
export interface DocumentoEvento {
  doc_id: string
  tipo_documento: string
  version_oficial: string | null
  version_ingesta: number
  estado: string
  paginas_total: number | null
  paginas_no_indexadas: number[]
  advertencias: string[]
}

export interface DocumentosEvento {
  evento_id: string
  documentos: DocumentoEvento[]
}

// Copia a mano de SesionSalida: src/licigt/consulta/api.py
export interface Sesion {
  usuario: string
  tenant_id: string
  rol: string
}
