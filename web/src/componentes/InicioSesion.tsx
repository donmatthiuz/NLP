import { useEffect, useId, useRef, useState } from 'react'

interface Props {
  error: string | null
  enviando: boolean
  alEntrar: (usuario: string, contrasena: string) => void
}

// La contraseña vive solo en el estado del formulario: nunca en un almacenamiento ni en la URL.
export function InicioSesion({ error, enviando, alEntrar }: Props) {
  const idUsuario = useId()
  const idContrasena = useId()
  const [usuario, setUsuario] = useState('')
  const [contrasena, setContrasena] = useState('')
  const titulo = useRef<HTMLHeadingElement>(null)
  useEffect(() => { titulo.current?.focus() }, [])
  useEffect(() => { if (error) setContrasena('') }, [error])
  return (
    <form
      className="sesion" aria-label="Inicio de sesión"
      onSubmit={(e) => { e.preventDefault(); if (usuario && contrasena) alEntrar(usuario.trim(), contrasena) }}
    >
      <h2 ref={titulo} tabIndex={-1}>Iniciar sesión</h2>
      {error && <p className="sesion__error" role="alert">{error}</p>}
      <div className="campo">
        <label htmlFor={idUsuario}>Usuario</label>
        <input id={idUsuario} type="text" autoComplete="username" required maxLength={64} value={usuario}
          onChange={(e) => setUsuario(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor={idContrasena}>Contraseña</label>
        <input id={idContrasena} type="password" autoComplete="current-password" required maxLength={256} value={contrasena}
          onChange={(e) => setContrasena(e.target.value)} />
      </div>
      <button type="submit" className="boton" disabled={enviando || !usuario || !contrasena}>
        {enviando ? 'Ingresando…' : 'Iniciar sesión'}
      </button>
    </form>
  )
}
