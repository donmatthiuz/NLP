import { useEffect, useId, useRef } from 'react'
import { Button } from './ui/button'

interface Props {
  titulo: string
  lineas: string[]
  textoConfirmar: string
  guardando: boolean
  alConfirmar: () => void
  alCancelar: () => void
}

// Diálogo modal nativo: el foco entra en el título, queda dentro y vuelve al botón de origen; Escape cancela.
export function Confirmacion({ titulo, lineas, textoConfirmar, guardando, alConfirmar, alCancelar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)
  const tituloRef = useRef<HTMLHeadingElement>(null)
  const id = useId()

  useEffect(() => {
    const origen = document.activeElement as HTMLElement | null
    const d = dialogo.current
    if (d && !d.open) d.showModal()
    tituloRef.current?.focus()
    return () => {
      if (d?.open) d.close()
      origen?.focus()
    }
  }, [])

  return (
    <dialog
      ref={dialogo} aria-labelledby={id} onCancel={(e) => { e.preventDefault(); alCancelar() }}
      className="m-auto w-[min(36rem,calc(100vw-2rem))] max-w-none gap-4 rounded-xl border-2 border-foreground bg-card p-4 text-card-foreground shadow-dialogo backdrop:bg-velo open:grid motion-safe:open:animate-confirmacion sm:p-6"
    >
      <div className="grid gap-1">
        <h2 id={id} ref={tituloRef} tabIndex={-1}>{titulo}</h2>
        <p className="text-sm text-muted-foreground">Nada se guarda hasta que confirme.</p>
      </div>
      <ul className="grid max-h-[50vh] gap-2 overflow-auto">
        {lineas.map((l, i) => <li key={i} className="border-l-3 border-input pl-3 wrap-anywhere">{l}</li>)}
      </ul>
      <div className="flex flex-wrap justify-end gap-3">
        <Button type="button" variant="outline" size="sm" onClick={alCancelar} disabled={guardando}>Cancelar</Button>
        <Button type="button" size="sm" onClick={alConfirmar} disabled={guardando}>
          {guardando ? 'Guardando…' : textoConfirmar}
        </Button>
      </div>
    </dialog>
  )
}
