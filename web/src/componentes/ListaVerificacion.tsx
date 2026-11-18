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
import { CLASE_CITA, textoPagina } from './Fuentes'
import { IconoInfo, IconoItem } from './Iconos'
import { Alert, AlertDescription } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card } from './ui/card'
import { Checkbox } from './ui/checkbox'
import { Label } from './ui/label'
import { RadioGroup, RadioGroupItem } from './ui/radio-group'

const CATEGORIAS = { administrativa: 'Administrativa', legal: 'Legal', tecnica: 'Técnica', financiera: 'Financiera' }
const CARACTERES = { fundamental: 'Fundamental', no_fundamental: 'No fundamental', no_indicado: 'No indicado' }
const TIPOS = { requisito: 'Requisito', fecha: 'Fecha' }
// Grupos de la lista: solo ordenan la vista; dentro de cada grupo se respeta el orden recibido.
const GRUPOS = [{ tipo: 'requisito', titulo: 'Requisitos' }, { tipo: 'fecha', titulo: 'Fechas' }] as const

// Con 403 recargar no ayuda: el rol no cambia.
export const ofreceRecargar = (codigo: string) => codigo !== 'rol_no_permitido'

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
  const idLeyenda = useId()
  return (
    <Card asChild className="gap-0 py-0 data-[revision=true]:border-2 data-[revision=true]:border-estado-revision">
      <li data-revision={i.requiere_revision}>
        {i.requiere_revision && (
          <p className="border-b-2 border-estado-revision bg-estado-revision-fondo px-4 py-3 font-semibold text-foreground forced-colors:border-[CanvasText]">
            Requiere revisión: {i.motivo_revision}
          </p>
        )}
        <div className="grid min-w-0 gap-3 p-4">
          <p className="flex flex-wrap gap-2">
            <Badge>{TIPOS[i.tipo]}</Badge>
            {i.categoria && <Badge>{CATEGORIAS[i.categoria]}</Badge>}
            <Badge>{CARACTERES[i.caracter]}</Badge>
            {etiqueta && <Badge variant="suave">{etiqueta}</Badge>}
          </p>
          <blockquote className={CLASE_CITA} lang="es" id={idCita}>{mostrarCita(cita)}</blockquote>
          <p className="text-sm text-muted-foreground wrap-anywhere">
            <span className="font-mono">{rotuloDocumento(f.doc_id, tipos)}</span>, {textoPagina(f)}; versión de ingesta v{f.version_ingesta};
            versión oficial: {f.version_oficial ?? 'No indicada'}
          </p>
          {guardado ? (
            <fieldset className="grid min-w-0 gap-2" disabled={soloLectura} aria-describedby={soloLectura ? idExplicacion : undefined}>
              <legend id={idLeyenda} className="mb-2 text-sm text-muted-foreground">Estado de «{nombre(i)}»</legend>
              <RadioGroup
                name={grupo} value={fila.estado} disabled={soloLectura} aria-labelledby={idLeyenda}
                onValueChange={(v) => alMarcar(v as EstadoItem)} className="flex flex-wrap gap-2"
              >
                {ESTADOS_ITEM.map((e) => (
                  <Label key={e} data-activo={fila.estado === e}
                    className="min-h-11 rounded-lg border border-input px-3 font-normal transition-colors hover:[&:not(:has(:disabled))]:bg-muted-hover has-disabled:text-muted-foreground data-[activo=true]:border-2 data-[activo=true]:border-foreground data-[activo=true]:bg-muted data-[activo=true]:font-semibold">
                    <RadioGroupItem value={e} />
                    <IconoItem estado={e} />
                    <span>{ROTULOS_ESTADO_ITEM[e]}</span>
                  </Label>
                ))}
              </RadioGroup>
            </fieldset>
          ) : (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Label className="min-h-11 pr-2 font-normal">
                <Checkbox checked={fila.incluir} onCheckedChange={alIncluir} disabled={soloLectura} aria-describedby={idCita} />
                <span>Incluir</span>
              </Label>
              <Badge variant="suave">No guardado</Badge>
            </div>
          )}
          {pendiente && (
            <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
              <Badge variant="aviso">Sin guardar</Badge>
              <span className="text-sm text-muted-foreground">{ROTULOS_ESTADO_ITEM[fila.estadoGuardado!]} a {ROTULOS_ESTADO_ITEM[fila.estado]}</span>
              <Button type="button" variant="outline" size="sm" disabled={soloLectura} onClick={(e) => alGuardarCambio(e.currentTarget)}>Guardar cambio</Button>
              <Button type="button" variant="outline" size="sm" onClick={alDescartar}>Descartar</Button>
            </div>
          )}
        </div>
      </li>
    </Card>
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
    <section className="grid gap-4" aria-labelledby="titulo-lista">
      <h2 id="titulo-lista" ref={titulo} tabIndex={-1}>Lista de verificación</h2>
      <Alert variant="neutro" className="text-sm font-semibold">
        <IconoInfo />
        <AlertDescription>Los estados de la lista no certifican cumplimiento.</AlertDescription>
      </Alert>
      <div className="grid gap-2">
        <div className="flex flex-wrap gap-3">
          <Button type="button" variant="outline" size="sm" onClick={() => void proponer()} disabled={cargando || soloLectura}>Proponer lista</Button>
          <Button
            type="button" size="sm" disabled={porGuardar.length === 0 || guardando || soloLectura}
            onClick={(e) => { origen.current = e.currentTarget; setConfirmando({ tipo: 'guardar', items: porGuardar }) }}
          >
            Guardar {porGuardar.length} {porGuardar.length === 1 ? 'ítem' : 'ítems'}
          </Button>
        </div>
        {soloLectura && <p id={idRol} className="text-sm text-muted-foreground">{MENSAJE_ROL}.</p>}
      </div>
      <div role="status" className="sr-only">{anuncio}</div>
      {aviso && (
        <Alert variant={aviso.tipo === 'conflicto' ? 'revision' : 'destructive'} role="alert" className="justify-items-start gap-3">
          <p className={aviso.tipo === 'conflicto' ? 'font-semibold' : undefined}>{aviso.texto}</p>
          {aviso.tipo !== 'ok' && ofreceRecargar(aviso.codigo ?? '') && <Button type="button" variant="outline" size="sm" onClick={() => void recargar()}>Recargar lista</Button>}
        </Alert>
      )}
      {abstencion && <p className="text-sm text-muted-foreground">{abstencion}</p>}
      {filas.length === 0 && !cargando && !abstencion && (
        <p className="p-4 text-sm text-muted-foreground">Todavía no hay ítems. Use «Proponer lista» para obtener una propuesta del evento; no se guarda nada hasta que usted lo confirme.</p>
      )}
      {GRUPOS.map(({ tipo, titulo: tituloGrupo }) => {
        const delGrupo = filas.filter((f) => f.item.tipo === tipo)
        if (delGrupo.length === 0) return null
        return (
          <div key={tipo} className="grid gap-3">
            <h3 className="flex items-baseline gap-2 border-b border-border pb-1">
              {tituloGrupo} <span className="text-sm font-normal text-muted-foreground">({delGrupo.length})</span>
            </h3>
            <ul className="grid gap-3">
              {delGrupo.map((f) => (
                <FilaItem
                  key={f.clave} fila={f} tipos={tipos} soloLectura={soloLectura} idExplicacion={idRol}
                  alIncluir={() => despachar({ tipo: 'alternarIncluir', clave: f.clave })}
                  alMarcar={(estado) => despachar({ tipo: 'marcar', clave: f.clave, estado })}
                  alGuardarCambio={(el) => { origen.current = el; setConfirmando({ tipo: 'cambio', fila: f }) }}
                  alDescartar={() => despachar({ tipo: 'descartarCambio', clave: f.clave })}
                />
              ))}
            </ul>
          </div>
        )
      })}
      {pendientes.length > 0 && <p className="text-sm text-muted-foreground">{pendientes.length === 1 ? "Hay 1 cambio sin guardar" : `Hay ${pendientes.length} cambios sin guardar`}; cada uno se confirma por separado.</p>}
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
