import { useEffect, useId, useRef, useState } from 'react'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { Input } from './ui/input'
import { Label } from './ui/label'

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
    <Card asChild className="mx-auto w-full max-w-sm gap-4 p-6 sm:mt-6">
      <form
        aria-label="Inicio de sesión"
        onSubmit={(e) => { e.preventDefault(); if (usuario && contrasena) alEntrar(usuario.trim(), contrasena) }}
      >
        <h2 ref={titulo} tabIndex={-1}>Iniciar sesión</h2>
        {error && <Alert variant="destructive" role="alert">{error}</Alert>}
        <div className="grid gap-2">
          <Label htmlFor={idUsuario}>Usuario</Label>
          <Input id={idUsuario} type="text" autoComplete="username" required maxLength={64} value={usuario}
            onChange={(e) => setUsuario(e.target.value)} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor={idContrasena}>Contraseña</Label>
          <Input id={idContrasena} type="password" autoComplete="current-password" required maxLength={256} value={contrasena}
            onChange={(e) => setContrasena(e.target.value)} />
        </div>
        <Button type="submit" className="self-start" disabled={enviando || !usuario || !contrasena}>
          {enviando ? 'Ingresando…' : 'Iniciar sesión'}
        </Button>
      </form>
    </Card>
  )
}
