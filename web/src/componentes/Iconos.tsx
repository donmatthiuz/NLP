import type { ReactNode } from 'react'
import type { Estado, EstadoItem } from '../tipos'

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg className="icono" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  )
}

const ICONOS: Record<Estado, ReactNode> = {
  respuesta: (<><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>),
  abstencion: (<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>),
  revision: (<><path d="M12 3l10 18H2z" /><path d="M12 10v5M12 18v.5" /></>),
  aclaracion: (<><path d="M4 5h16v11H10l-4 4v-4H4z" /><path d="M10 9.5a2 2 0 1 1 3 1.7c-.6.4-1 .7-1 1.3M12 14.5v.5" /></>),
}

export const IconoEstado = ({ estado }: { estado: Estado }) => <Svg>{ICONOS[estado]}</Svg>

export const IconoInfo = () => (
  <Svg><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.5" /></Svg>
)

export const IconoCobertura = () => (
  <Svg><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /><path d="M9 12h6" strokeDasharray="2 2" /><path d="M9 16h6" strokeDasharray="2 2" /></Svg>
)

const ICONOS_ITEM: Record<EstadoItem, ReactNode> = {
  pendiente: (<circle cx="12" cy="12" r="9" />),
  preparado: (<><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></>),
  revisado: (<><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>),
}

export const IconoItem = ({ estado }: { estado: EstadoItem }) => <Svg>{ICONOS_ITEM[estado]}</Svg>
