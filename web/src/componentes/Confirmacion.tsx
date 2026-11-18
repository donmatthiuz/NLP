import { useEffect, useId, useRef } from 'react'

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
    <dialog ref={dialogo} className="confirmacion" aria-labelledby={id} onCancel={(e) => { e.preventDefault(); alCancelar() }}>
      <h2 id={id} ref={tituloRef} tabIndex={-1}>{titulo}</h2>
      <p className="ayuda">Nada se guarda hasta que confirme.</p>
      <ul className="confirmacion__lineas">
        {lineas.map((l, i) => <li key={i}>{l}</li>)}
      </ul>
      <div className="confirmacion__acciones">
        <button type="button" className="boton boton--secundario" onClick={alCancelar} disabled={guardando}>Cancelar</button>
        <button type="button" className="boton" onClick={alConfirmar} disabled={guardando}>
          {guardando ? 'Guardando…' : textoConfirmar}
        </button>
      </div>
    </dialog>
  )
}
