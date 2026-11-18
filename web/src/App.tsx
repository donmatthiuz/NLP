import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ErrorConsulta, ErrorNoAutenticado, alPerderSesion, cerrarSesionApi, consultarApi, iniciarSesionApi, obtenerSesionApi,
} from './api'
import { InicioSesion } from './componentes/InicioSesion'
import { IconoInfo } from './componentes/Iconos'
import { DocumentosEvento, useDocumentosEvento } from './componentes/DocumentosEvento'
import { Resultado } from './componentes/Resultado'
import { ZonaFuentes } from './componentes/Fuentes'
import { ListaVerificacion } from './componentes/ListaVerificacion'
import { SelectorTema } from './componentes/Tema'
import { Alert, AlertDescription } from './componentes/ui/alert'
import { Button } from './componentes/ui/button'
import { Card } from './componentes/ui/card'
import { Label } from './componentes/ui/label'
import { NativeSelect, NativeSelectOption } from './componentes/ui/native-select'
import { Textarea } from './componentes/ui/textarea'
import { mapaTipos } from './cobertura'
import { EJEMPLOS } from './ejemplos'
import { MENSAJE_SESION_TERMINADA, ROTULOS, alAclarar, estadoDe, textoSesion } from './estado'
import type { RespuestaEstructurada, Sesion } from './tipos'

const MODO_EJEMPLOS = (import.meta.env.VITE_MODO ?? (import.meta.env.DEV ? 'ejemplos' : 'api')) === 'ejemplos'
const EVENTO_ID = import.meta.env.VITE_EVENTO_ID ?? '222-IGSS-2023'
const MAXIMO = 500
// Contenedor de lectura: 60rem, 16 px de margen lateral y 24 px desde 40rem (DISENO.md, "Rejilla y ancho").
const CONTENEDOR = 'mx-auto w-full max-w-lectura px-4 sm:px-6'
const PRINCIPAL = `${CONTENEDOR} grid grid-cols-[minmax(0,1fr)] gap-6 py-6 lg:gap-8 lg:py-8`

type Situacion =
  | { tipo: 'vacia' }
  | { tipo: 'cargando' }
  | { tipo: 'error'; motivo: string }
  | { tipo: 'resultado'; respuesta: RespuestaEstructurada; pregunta: string }

export default function App() {
  const [ejemploId, setEjemploId] = useState(EJEMPLOS[0].id)
  const [texto, setTexto] = useState(MODO_EJEMPLOS ? EJEMPLOS[0].pregunta : '')
  const [situacion, setSituacion] = useState<Situacion>({ tipo: 'vacia' })
  // undefined: comprobando; null: sin sesión (pantalla de inicio); en modo ejemplos no hay sesión.
  const [sesion, setSesion] = useState<Sesion | null | undefined>(MODO_EJEMPLOS ? null : undefined)
  const [errorSesion, setErrorSesion] = useState<string | null>(null)
  const [entrando, setEntrando] = useState(false)
  const [anuncio, setAnuncio] = useState('')
  const conSesion = MODO_EJEMPLOS || !!sesion
  const documentos = useDocumentosEvento(EVENTO_ID, MODO_EJEMPLOS, conSesion)
  const tipos = useMemo(() => (documentos.tipo === 'listo' ? mapaTipos(documentos.datos.documentos) : undefined), [documentos])
  const cajaRef = useRef<HTMLTextAreaElement>(null)
  const rotuloRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (MODO_EJEMPLOS) return
    alPerderSesion(() => { setSesion(null); setErrorSesion(MENSAJE_SESION_TERMINADA); setSituacion({ tipo: 'vacia' }) })
    obtenerSesionApi()
      .then(setSesion)
      .catch((e) => { setSesion(null); setErrorSesion(e instanceof Error ? e.message : 'Error inesperado') })
    return () => alPerderSesion(null)
  }, [])

  // Al entrar, el foco va a la caja de pregunta.
  useEffect(() => { if (!MODO_EJEMPLOS && sesion) cajaRef.current?.focus() }, [sesion])

  const entrar = async (usuario: string, contrasena: string) => {
    setEntrando(true)
    setErrorSesion(null)
    try {
      await iniciarSesionApi(usuario, contrasena)
      setSesion(await obtenerSesionApi())
    } catch (e) {
      setErrorSesion(e instanceof Error ? e.message : 'Error inesperado')
    } finally {
      setEntrando(false)
    }
  }

  const salir = async () => {
    try { await cerrarSesionApi() } catch { /* la cookie se borra en el servidor; si no responde, igual se vuelve al inicio */ }
    setSesion(null)
    setSituacion({ tipo: 'vacia' })
    setTexto('')
  }

  useEffect(() => {
    if (situacion.tipo !== 'resultado') return
    rotuloRef.current?.focus()
    setAnuncio(`Resultado: ${ROTULOS[estadoDe(situacion.respuesta)]}`)
    if (estadoDe(situacion.respuesta) === 'aclaracion') {
      const { texto: conservado, cursor } = alAclarar(situacion.pregunta)
      setTexto(conservado)
      requestAnimationFrame(() => cajaRef.current?.setSelectionRange(cursor, cursor))
    }
  }, [situacion])

  const elegirEjemplo = (id: string) => {
    setEjemploId(id)
    setTexto(EJEMPLOS.find((e) => e.id === id)!.pregunta)
  }

  const consultar = async () => {
    const pregunta = texto.trim()
    if (!pregunta || situacion.tipo === 'cargando') return
    setSituacion({ tipo: 'cargando' })
    setAnuncio('Consultando. Puede tardar unos segundos.')
    if (MODO_EJEMPLOS) {
      const ejemplo = EJEMPLOS.find((e) => e.id === ejemploId)!
      setSituacion({ tipo: 'resultado', respuesta: ejemplo.respuesta, pregunta })
      return
    }
    try {
      const respuesta = await consultarApi(EVENTO_ID, pregunta)
      setSituacion({ tipo: 'resultado', respuesta, pregunta })
    } catch (e) {
      // El 401 ya devolvió a la pantalla de inicio de sesión y la pregunta sigue en la caja.
      if (e instanceof ErrorNoAutenticado) return
      const motivo = e instanceof ErrorConsulta ? e.message : 'Error inesperado'
      setSituacion({ tipo: 'error', motivo })
      setAnuncio(`No se pudo completar la consulta. ${motivo}`)
    }
  }

  const cargando = situacion.tipo === 'cargando'
  const r = situacion.tipo === 'resultado' ? situacion.respuesta : null
  const estado = r ? estadoDe(r) : null

  return (
    <>
      {MODO_EJEMPLOS && <p className="border-b border-border bg-muted px-4 py-2 text-sm">Modo ejemplos: respuestas fijas, no se consulta la API.</p>}
      <header className="border-b border-border bg-card">
        <div className={`${CONTENEDOR} flex flex-wrap items-start justify-between gap-4 py-4`}>
          <div className="grid gap-1">
            <div>
              <h1>LiciGT</h1>
              <p className="text-muted-foreground">Consulta de licitaciones</p>
            </div>
            <p className="font-semibold">Evento {EVENTO_ID}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {sesion && (
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className="wrap-anywhere">{textoSesion(sesion)}</span>
                <Button type="button" variant="outline" size="sm" onClick={() => void salir()}>Cerrar sesión</Button>
              </p>
            )}
            <SelectorTema />
          </div>
        </div>
      </header>
      {!conSesion ? (
        <main className={PRINCIPAL}>
          {sesion === undefined
            ? <p className="p-4 text-sm text-muted-foreground" aria-busy="true">Comprobando la sesión…</p>
            : <InicioSesion error={errorSesion} enviando={entrando} alEntrar={(u, c) => void entrar(u, c)} />}
        </main>
      ) : (
      <main className={PRINCIPAL}>
        <DocumentosEvento carga={documentos} />
        <Card asChild className="gap-4 p-4 sm:p-6">
          <form
            aria-label="Consulta"
            onSubmit={(e) => { e.preventDefault(); void consultar() }}
          >
            {MODO_EJEMPLOS && (
              <div className="grid gap-2">
                <Label htmlFor="ejemplo">Ejemplo</Label>
                <NativeSelect id="ejemplo" className="w-full" value={ejemploId} onChange={(e) => elegirEjemplo(e.target.value)}>
                  {EJEMPLOS.map((e) => <NativeSelectOption key={e.id} value={e.id}>{e.titulo}</NativeSelectOption>)}
                </NativeSelect>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="pregunta">Pregunta sobre el evento</Label>
              <Textarea
                id="pregunta" ref={cajaRef} rows={3} maxLength={MAXIMO} value={texto}
                aria-describedby="contador"
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void consultar() }
                }}
              />
            </div>
            <div className="flex items-center justify-end gap-4">
              <span id="contador" className="text-xs text-muted-foreground" aria-live={texto.length > 450 ? 'polite' : 'off'}>
                {texto.length}/{MAXIMO}
              </span>
              <Button type="submit" disabled={cargando || !texto.trim()}>
                {cargando ? 'Consultando…' : 'Consultar'}
              </Button>
            </div>
          </form>
        </Card>

        <Alert variant="neutro" className="text-sm font-semibold">
          <IconoInfo />
          <AlertDescription>La respuesta se basa en los documentos cargados del evento</AlertDescription>
        </Alert>
        <div role="status" className="sr-only">{anuncio}</div>

        {situacion.tipo === 'vacia' && (
          <p className="p-4 text-sm text-muted-foreground">Escriba una pregunta sobre los documentos del evento. Cada dato de la respuesta trae su fuente.</p>
        )}
        {cargando && <p className="p-4 text-sm text-muted-foreground" aria-busy="true">Consultando…</p>}
        {situacion.tipo === 'error' && (
          <Alert variant="destructive" className="gap-2 rounded-xl p-4">
            <h2 className="text-destructive">No se pudo completar la consulta</h2>
            <p>{situacion.motivo}</p>
          </Alert>
        )}
        {r && estado && (
          <>
            <Resultado
              ref={rotuloRef} respuesta={r} pregunta={situacion.tipo === 'resultado' ? situacion.pregunta : ''}
              alEscribirAclaracion={() => {
                const caja = cajaRef.current
                if (!caja) return
                caja.focus()
                caja.setSelectionRange(caja.value.length, caja.value.length)
              }}
            />
            {estado !== 'aclaracion' && (
              <ZonaFuentes fuentes={r.sources} abstencion={r.abstained} conflicto={r.needs_human_review} tipos={tipos}
                eventoId={MODO_EJEMPLOS ? undefined : EVENTO_ID} />
            )}
          </>
        )}
        <ListaVerificacion eventoId={EVENTO_ID} modoEjemplos={MODO_EJEMPLOS} tipos={tipos} soloLectura={sesion?.rol === 'lector'} />
      </main>
      )}
      <footer className="border-t border-border py-6 text-sm text-muted-foreground">
        <div className={CONTENEDOR}>LiciGT, proyecto CC3103 (UVG). No presenta ofertas ni decide la vigencia de documentos.</div>
      </footer>
    </>
  )
}
