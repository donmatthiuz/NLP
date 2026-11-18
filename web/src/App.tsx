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
import { mapaTipos } from './cobertura'
import { EJEMPLOS } from './ejemplos'
import { MENSAJE_SESION_TERMINADA, ROTULOS, alAclarar, estadoDe, textoSesion } from './estado'
import type { RespuestaEstructurada, Sesion } from './tipos'

const MODO_EJEMPLOS = (import.meta.env.VITE_MODO ?? (import.meta.env.DEV ? 'ejemplos' : 'api')) === 'ejemplos'
const EVENTO_ID = import.meta.env.VITE_EVENTO_ID ?? '222-IGSS-2023'
const MAXIMO = 500

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
      {MODO_EJEMPLOS && <p className="aviso-modo">Modo ejemplos: respuestas fijas, no se consulta la API.</p>}
      <header className="encabezado">
        <div className="contenedor encabezado__interior">
          <div>
            <h1>LiciGT</h1>
            <p className="encabezado__sub">Consulta de licitaciones</p>
            <p className="encabezado__evento">Evento {EVENTO_ID}</p>
          </div>
          <div className="encabezado__acciones">
            {sesion && (
              <p className="encabezado__sesion">
                <span>{textoSesion(sesion)}</span>
                <button type="button" className="boton boton--secundario" onClick={() => void salir()}>Cerrar sesión</button>
              </p>
            )}
            <SelectorTema />
          </div>
        </div>
      </header>
      {!conSesion ? (
        <main className="contenedor">
          {sesion === undefined
            ? <p className="ayuda vacia" aria-busy="true">Comprobando la sesión…</p>
            : <InicioSesion error={errorSesion} enviando={entrando} alEntrar={(u, c) => void entrar(u, c)} />}
        </main>
      ) : (
      <main className="contenedor">
        <DocumentosEvento carga={documentos} />
        <form
          className="consulta"
          aria-label="Consulta"
          onSubmit={(e) => { e.preventDefault(); void consultar() }}
        >
          {MODO_EJEMPLOS && (
            <div className="campo">
              <label htmlFor="ejemplo">Ejemplo</label>
              <select id="ejemplo" value={ejemploId} onChange={(e) => elegirEjemplo(e.target.value)}>
                {EJEMPLOS.map((e) => <option key={e.id} value={e.id}>{e.titulo}</option>)}
              </select>
            </div>
          )}
          <div className="campo">
            <label htmlFor="pregunta">Pregunta sobre el evento</label>
            <textarea
              id="pregunta" ref={cajaRef} rows={3} maxLength={MAXIMO} value={texto}
              aria-describedby="contador"
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void consultar() }
              }}
            />
          </div>
          <div className="consulta__pie">
            <span id="contador" className="contador" aria-live={texto.length > 450 ? 'polite' : 'off'}>
              {texto.length}/{MAXIMO}
            </span>
            <button type="submit" className="boton" disabled={cargando || !texto.trim()}>
              {cargando ? 'Consultando…' : 'Consultar'}
            </button>
          </div>
        </form>

        <p className="aviso-fijo">
          <IconoInfo />
          <span>La respuesta se basa en los documentos cargados del evento</span>
        </p>
        <div role="status" className="oculto-visual">{anuncio}</div>

        {situacion.tipo === 'vacia' && (
          <p className="ayuda vacia">Escriba una pregunta sobre los documentos del evento. Cada dato de la respuesta trae su fuente.</p>
        )}
        {cargando && <p className="ayuda vacia" aria-busy="true">Consultando…</p>}
        {situacion.tipo === 'error' && (
          <section className="error-consulta">
            <h2>No se pudo completar la consulta</h2>
            <p>{situacion.motivo}</p>
          </section>
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
      <footer className="pie">
        <div className="contenedor">LiciGT, proyecto CC3103 (UVG). No presenta ofertas ni decide la vigencia de documentos.</div>
      </footer>
    </>
  )
}
