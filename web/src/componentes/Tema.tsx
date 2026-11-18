import { useState } from 'react'
import { Label } from './ui/label'
import { NativeSelect, NativeSelectOption } from './ui/native-select'

type Tema = 'sistema' | 'claro' | 'oscuro'
const CLAVE = 'licigt-tema'

function guardado(): Tema {
  try {
    const t = localStorage.getItem(CLAVE)
    return t === 'claro' || t === 'oscuro' ? t : 'sistema'
  } catch {
    return 'sistema'
  }
}

export function SelectorTema() {
  const [tema, setTema] = useState<Tema>(guardado)
  const cambiar = (t: Tema) => {
    setTema(t)
    if (t === 'sistema') delete document.documentElement.dataset.tema
    else document.documentElement.dataset.tema = t
    try {
      if (t === 'sistema') localStorage.removeItem(CLAVE)
      else localStorage.setItem(CLAVE, t)
    } catch { /* sin almacenamiento: sigue la elección en esta sesión */ }
  }
  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="tema" className="text-sm">Tema</Label>
      <NativeSelect id="tema" value={tema} onChange={(e) => cambiar(e.target.value as Tema)}>
        <NativeSelectOption value="sistema">Sistema</NativeSelectOption>
        <NativeSelectOption value="claro">Claro</NativeSelectOption>
        <NativeSelectOption value="oscuro">Oscuro</NativeSelectOption>
      </NativeSelect>
    </div>
  )
}
