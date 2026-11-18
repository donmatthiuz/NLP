import { useEffect, useId, useMemo, useReducer, useRef, useState } from 'react'
import { rotuloDocumento } from '../cobertura'
import type { MapaTipos } from '../cobertura'
import { ErrorLista, ErrorNoAutenticado, MENSAJE_ROL, cambiarEstadoApi, guardarApi, listarApi, proponerApi } from '../api'
import { crearListaEjemplos } from '../listaEjemplos'
import {
  ESTADOS_ITEM, ROTULOS_ESTADO_ITEM, cambiosPendientes, itemsAGuardar, mostrarCita, partesItem, reducirLista, sinGuardar,
} from '../lista'
import type { FilaLista } from '../lista'
import type { EstadoItem, ItemLista, ItemPropuesto, PropuestaLista } from '../tipos'
import { Confirmacion } from './Confirmacion'
import { IconoItem } from './Iconos'

const CATEGORIAS = { administrativa: 'Administrativa', legal: 'Legal', tecnica: 'Técnica', financiera: 'Financiera' }
const CARACTERES = { fundamental: 'Fundamental', no_fundamental: 'No fundamental', no_indicado: 'No indicado' }
const TIPOS = { requisito: 'Requisito', fecha: 'Fecha' }

// Con 403 recargar no ayuda: el rol no cambia.
export const ofreceRecargar = (codigo: string) => codigo !== 'rol_no_permitido'

const paginas = (p: number, fin: number | null) => (fin === null || fin === p ? `p. ${p}` : `pp. ${p}–${fin}`)
const nombre = (i: ItemPropuesto) => `${TIPOS[i.tipo]}${i.categoria ? ` ${CATEGORIAS[i.categoria].toLowerCase()}` : ''}`

type Confirmando =
  | { tipo: 'guardar'; items: ItemPropuesto[] }
  | { tipo: 'cambio'; fila: FilaLista }

interface ApiLista {
  proponer: () => Promise<PropuestaLista>
  listar: () => Promise<ItemLista[]>
  guardar: (items: ItemPropuesto[], confirmado: boolean) => Promise<ItemLista[]>
  cambiarEstado: (itemId: string, anterior: EstadoItem, nuevo: EstadoItem, confirmado: boolean) => Promise<ItemLista>
}

export function FilaItem({ fila, tipos, soloLectura = false, idExplicacion, alIncluir, alMarcar, alGuardarCambio, alDescartar }: {
  fila: FilaLista
  tipos?: MapaTipos
  soloLectura?: boolean
  idExplicacion?: string
  alIncluir: () => void
  alMarcar: (e: EstadoItem) => void
  alGuardarCambio: (origen: HTMLElement) => void
  alDescartar: () => void
}) {
  const { item: i } = fila
  const f = i.fuentes[0]
  const grupo = useId()
  const idCita = useId()
  const { etiqueta, cita } = partesItem(i)
  const guardado = fila.itemId !== null
  const pendiente = sinGuardar(fila)
  return (
    <li className="item-lista" data-revision={i.requiere_revision}>
      {i.requiere_revision && (
        <p className="banda-revision">Requiere revisión: {i.motivo_revision}</p>
      )}
      <div className="item-lista__cuerpo">
        <p className="item-lista__rotulos">
          <span className="etiqueta">{TIPOS[i.tipo]}</span>
          {i.categoria && <span className="etiqueta">{CATEGORIAS[i.categoria]}</span>}
          <span className="etiqueta">{CARACTERES[i.caracter]}</span>
          {etiqueta && <span className="etiqueta etiqueta--suave">{etiqueta}</span>}
        </p>
        <blockquote className="cita" lang="es" id={idCita}>{mostrarCita(cita)}</blockquote>
        <p className="item-lista__origen">
          <span className="mono">{rotuloDocumento(f.doc_id, tipos)}</span>, {paginas(f.page, f.page_end)}; versión de ingesta v{f.version_ingesta};
          versión oficial: {f.version_oficial ?? 'No indicada'}
        </p>
        {guardado ? (
          <fieldset className="estados" disabled={soloLectura} aria-describedby={soloLectura ? idExplicacion : undefined}>
            <legend>Estado de «{nombre(i)}»</legend>
            {ESTADOS_ITEM.map((e) => (
              <label key={e} className="estados__opcion" data-activo={fila.estado === e}>
                <input type="radio" name={grupo} checked={fila.estado === e} disabled={soloLectura} onChange={() => alMarcar(e)} />
                <IconoItem estado={e} />
                <span>{ROTULOS_ESTADO_ITEM[e]}</span>
              </label>
            ))}
          </fieldset>
        ) : (
          <label className="incluir">
            <input type="checkbox" checked={fila.incluir} onChange={alIncluir} aria-describedby={idCita} />
            <span>Incluir</span>
            <span className="etiqueta etiqueta--suave">No guardado</span>
          </label>
        )}
        {pendiente && (
          <div className="item-lista__cambio">
            <span className="etiqueta etiqueta--aviso">Sin guardar</span>
            <span className="ayuda">{ROTULOS_ESTADO_ITEM[fila.estadoGuardado!]} a {ROTULOS_ESTADO_ITEM[fila.estado]}</span>
            <button type="button" className="boton boton--secundario" disabled={soloLectura} onClick={(e) => alGuardarCambio(e.currentTarget)}>Guardar cambio</button>
            <button type="button" className="boton boton--secundario" onClick={alDescartar}>Descartar</button>
          </div>
        )}
      </div>
    </li>
  )
}

export function ListaVerificacion({ eventoId, modoEjemplos, tipos, soloLectura = false }: { eventoId: string; modoEjemplos: boolean; tipos?: MapaTipos; soloLectura?: boolean }) {
  const api = useMemo<ApiLista>(() => {
    if (modoEjemplos) {
      const e = crearListaEjemplos(eventoId, new URLSearchParams(window.location.search).get('conflicto') === '1')
      return { proponer: e.proponer, listar: e.listar, guardar: (i) => e.guardar(i), cambiarEstado: (id, a, n) => e.cambiarEstado(id, a, n) }
    }
    return {
      proponer: () => proponerApi(eventoId),
      listar: () => listarApi(eventoId),
      guardar: (items, c) => guardarApi(eventoId, items, c),
      cambiarEstado: (id, a, n, c) => cambiarEstadoApi(eventoId, id, a, n, c),
    }
  }, [eventoId, modoEjemplos])

  const idRol = useId()
  const [filas, despachar] = useReducer(reducirLista, [] as FilaLista[])
  const [confirmando, setConfirmando] = useState<Confirmando | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [cargando, setCargando] = useState(false)
  const [aviso, setAviso] = useState<{ tipo: 'error' | 'conflicto' | 'ok'; texto: string; codigo?: string } | null>(null)
  const [abstencion, setAbstencion] = useState<string | null>(null)
  const [anuncio, setAnuncio] = useState('')
  const origen = useRef<HTMLElement | null>(null)
  const titulo = useRef<HTMLHeadingElement>(null)

  const recargar = async () => {
    setCargando(true)
    try {
      despachar({ tipo: 'cargar', items: await api.listar() })
      setAviso(null)
    } catch (e) {
      if (e instanceof ErrorNoAutenticado) return
      setAviso({ tipo: 'error', texto: e instanceof ErrorLista ? e.message : 'Error inesperado', codigo: e instanceof ErrorLista ? e.codigo : undefined })
    } finally {
      setCargando(false)
    }
  }

  useEffect(() => { void recargar() }, [api]) // eslint-disable-line react-hooks/exhaustive-deps

  const proponer = async () => {
    setCargando(true)
    setAviso(null)
    setAbstencion(null)
    try {
      const p = await api.proponer()
      despachar({ tipo: 'proponer', items: p.items })
      if (p.items.length === 0) setAbstencion(p.respuesta.abstained ? 'No hay información suficiente en los documentos para proponer ítems.' : 'La propuesta no trae ítems nuevos.')
      setAnuncio(`Propuesta: ${p.items.length} ítems`)
    } catch (e) {
      if (e instanceof ErrorNoAutenticado) return
      setAviso({ tipo: 'error', texto: e instanceof ErrorLista ? e.message : 'Error inesperado', codigo: e instanceof ErrorLista ? e.codigo : undefined })
    } finally {
      setCargando(false)
    }
  }

  const porGuardar = itemsAGuardar(filas)
  const pendientes = cambiosPendientes(filas)

  const confirmar = async () => {
    if (!confirmando) return
    setGuardando(true)
    try {
      // Solo este botón construye confirmado: true.
      if (confirmando.tipo === 'guardar') {
        despachar({ tipo: 'guardadas', items: await api.guardar(confirmando.items, true) })
        setAnuncio(`${confirmando.items.length} ítems guardados`)
      } else {
        const { fila } = confirmando
        despachar({ tipo: 'cambioGuardado', item: await api.cambiarEstado(fila.itemId!, fila.estadoGuardado!, fila.estado, true) })
        setAnuncio('Estado guardado')
      }
      setAviso(null)
    } catch (e) {
      if (e instanceof ErrorNoAutenticado) return
      const error = e instanceof ErrorLista ? e : new ErrorLista('Error inesperado', 'desconocido')
      if (error.codigo === 'estado_desactualizado' && confirmando.tipo === 'cambio') {
        despachar({ tipo: 'descartarCambio', clave: confirmando.fila.clave })
        setAviso({ tipo: 'conflicto', texto: error.message })
      } else {
        setAviso({ tipo: 'error', texto: error.message, codigo: error.codigo })
      }
    } finally {
      setGuardando(false)
      setConfirmando(null)
    }
  }

  const lineas = !confirmando ? [] : confirmando.tipo === 'guardar'
    ? confirmando.items.map((i) => `${nombre(i)}: ${mostrarCita(i.descripcion)} (se guarda como Pendiente)`)
    : [`${nombre(confirmando.fila.item)}: ${ROTULOS_ESTADO_ITEM[confirmando.fila.estadoGuardado!]} a ${ROTULOS_ESTADO_ITEM[confirmando.fila.estado]}`]

  return (
    <section className="lista" aria-labelledby="titulo-lista">
      <h2 id="titulo-lista" ref={titulo} tabIndex={-1}>Lista de verificación</h2>
      <p className="aviso-fijo"><span>Los estados de la lista no certifican cumplimiento.</span></p>
      <div className="lista__acciones">
        <button type="button" className="boton boton--secundario" onClick={() => void proponer()} disabled={cargando || soloLectura}>Proponer lista</button>
        <button
          type="button" className="boton" disabled={porGuardar.length === 0 || guardando || soloLectura}
          onClick={(e) => { origen.current = e.currentTarget; setConfirmando({ tipo: 'guardar', items: porGuardar }) }}
        >
          Guardar {porGuardar.length} {porGuardar.length === 1 ? 'ítem' : 'ítems'}
        </button>
      </div>
      {soloLectura && <p id={idRol} className="ayuda">{MENSAJE_ROL}.</p>}
      <div role="status" className="oculto-visual">{anuncio}</div>
      {aviso && (
        <div className={`lista__aviso lista__aviso--${aviso.tipo}`} role="alert">
          <p>{aviso.texto}</p>
          {aviso.tipo !== 'ok' && ofreceRecargar(aviso.codigo ?? '') && <button type="button" className="boton boton--secundario" onClick={() => void recargar()}>Recargar lista</button>}
        </div>
      )}
      {abstencion && <p className="ayuda">{abstencion}</p>}
      {filas.length === 0 && !cargando && !abstencion && (
        <p className="ayuda vacia">Todavía no hay ítems. Use «Proponer lista» para obtener una propuesta del evento; no se guarda nada hasta que usted lo confirme.</p>
      )}
      {filas.length > 0 && (
        <ul className="lista__items">
          {filas.map((f) => (
            <FilaItem
              key={f.clave} fila={f} tipos={tipos} soloLectura={soloLectura} idExplicacion={idRol}
              alIncluir={() => despachar({ tipo: 'alternarIncluir', clave: f.clave })}
              alMarcar={(estado) => despachar({ tipo: 'marcar', clave: f.clave, estado })}
              alGuardarCambio={(el) => { origen.current = el; setConfirmando({ tipo: 'cambio', fila: f }) }}
              alDescartar={() => despachar({ tipo: 'descartarCambio', clave: f.clave })}
            />
          ))}
        </ul>
      )}
      {pendientes.length > 0 && <p className="ayuda">{pendientes.length === 1 ? "Hay 1 cambio sin guardar" : `Hay ${pendientes.length} cambios sin guardar`}; cada uno se confirma por separado.</p>}
      {confirmando && (
        <Confirmacion
          titulo={confirmando.tipo === 'guardar' ? `Guardar ${confirmando.items.length} ${confirmando.items.length === 1 ? 'ítem' : 'ítems'}` : 'Guardar el cambio de estado'}
          lineas={lineas}
          textoConfirmar="Confirmar y guardar"
          guardando={guardando}
          alConfirmar={() => void confirmar()}
          alCancelar={() => setConfirmando(null)}
        />
      )}
    </section>
  )
}
