import { useEffect, useState } from 'react'
import { MoonIcon, SunIcon } from 'lucide-react'
import { Button } from './ui/button'

type Tema = 'claro' | 'oscuro'
const CLAVE = 'licigt-tema'
const PREFERENCIA_OSCURA = '(prefers-color-scheme: dark)'
const TEMAS = {
  claro: { nombre: 'Claro', siguiente: 'oscuro', Icono: SunIcon },
  oscuro: { nombre: 'Oscuro', siguiente: 'claro', Icono: MoonIcon },
} as const

function guardado(): Tema | null {
  try {
    const t = localStorage.getItem(CLAVE)
    return t === 'claro' || t === 'oscuro' ? t : null
  } catch {
    return null
  }
}

export function SelectorTema() {
  const [preferencia, setPreferencia] = useState<Tema | null>(guardado)
  const [temaSistema, setTemaSistema] = useState<Tema>(() => (
    typeof window !== 'undefined' && window.matchMedia(PREFERENCIA_OSCURA).matches ? 'oscuro' : 'claro'
  ))
  useEffect(() => {
    if (preferencia !== null) return
    const medio = window.matchMedia(PREFERENCIA_OSCURA)
    const actualizar = () => setTemaSistema(medio.matches ? 'oscuro' : 'claro')
    medio.addEventListener('change', actualizar)
    actualizar()
    return () => medio.removeEventListener('change', actualizar)
  }, [preferencia])
  const tema = preferencia ?? temaSistema
  const { nombre, siguiente, Icono } = TEMAS[tema]
  const descripcion = `Tema actual: ${nombre}. Cambiar a ${TEMAS[siguiente].nombre}.`
  const cambiar = (t: Tema) => {
    setPreferencia(t)
    document.documentElement.dataset.tema = t
    try {
      localStorage.setItem(CLAVE, t)
    } catch { /* sin almacenamiento: sigue la elección en esta sesión */ }
  }
  return (
    <Button id="tema" type="button" variant="outline" size="icon"
      aria-label={descripcion} title={descripcion} onClick={() => cambiar(siguiente)}>
      <Icono aria-hidden="true" />
    </Button>
  )
}
