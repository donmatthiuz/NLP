import { useState } from 'react'

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
    <div className="tema">
      <label htmlFor="tema">Tema</label>
      <select id="tema" value={tema} onChange={(e) => cambiar(e.target.value as Tema)}>
        <option value="sistema">Sistema</option>
        <option value="claro">Claro</option>
        <option value="oscuro">Oscuro</option>
      </select>
    </div>
  )
}
