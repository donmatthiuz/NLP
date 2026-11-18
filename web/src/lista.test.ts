import { afterEach, describe, expect, it, vi } from 'vitest'
import { EJEMPLO_PROPUESTA } from './ejemplos'
import { MENSAJE_CONFLICTO, ErrorLista, cambiarEstadoApi, guardarApi, listarApi, proponerApi } from './api'
import { cambiosPendientes, itemsAGuardar, mostrarCita, reducirLista, sinGuardar } from './lista'
import type { FilaLista } from './lista'
import type { ItemLista } from './tipos'

const propuestos = EJEMPLO_PROPUESTA.items

const guardado = (i: number, estado: ItemLista['estado'] = 'pendiente'): ItemLista => ({
  ...propuestos[i], item_id: `id-${i}`, evento_id: '222-IGSS-2023', estado,
  creado_por: 'demo', creado_en: '2026-11-17T12:00:00Z', actualizado_por: 'demo', actualizado_en: '2026-11-17T12:00:00Z',
})

const conPropuesta = (): FilaLista[] => reducirLista([], { tipo: 'proponer', items: propuestos })

describe('reductor de la lista', () => {
  it('proponer deja filas sin guardar, incluidas y pendientes', () => {
    const filas = conPropuesta()
    expect(filas).toHaveLength(propuestos.length)
    expect(filas.every((f) => f.itemId === null && f.incluir && f.estado === 'pendiente')).toBe(true)
    expect(itemsAGuardar(filas)).toEqual(propuestos)
  })

  it('alternar la inclusión saca el ítem de lo que se guarda', () => {
    const filas = reducirLista(conPropuesta(), { tipo: 'alternarIncluir', clave: conPropuesta()[0].clave })
    expect(itemsAGuardar(filas)).toEqual(propuestos.slice(1))
  })

  it('marcar solo cambia ítems guardados', () => {
    const sin = reducirLista(conPropuesta(), { tipo: 'marcar', clave: conPropuesta()[0].clave, estado: 'revisado' })
    expect(sin.every((f) => f.estado === 'pendiente')).toBe(true)
    const filas = reducirLista([], { tipo: 'cargar', items: [guardado(0)] })
    const marcadas = reducirLista(filas, { tipo: 'marcar', clave: filas[0].clave, estado: 'preparado' })
    expect(marcadas[0].estado).toBe('preparado')
    expect(marcadas[0].estadoGuardado).toBe('pendiente')
    expect(sinGuardar(marcadas[0])).toBe(true)
    expect(cambiosPendientes(marcadas)).toHaveLength(1)
  })

  it('volver al estado guardado quita la marca Sin guardar', () => {
    const filas = reducirLista([], { tipo: 'cargar', items: [guardado(0)] })
    const a = reducirLista(filas, { tipo: 'marcar', clave: filas[0].clave, estado: 'revisado' })
    const b = reducirLista(a, { tipo: 'marcar', clave: filas[0].clave, estado: 'pendiente' })
    expect(sinGuardar(b[0])).toBe(false)
  })

  it('descartar el cambio devuelve el estado guardado', () => {
    const filas = reducirLista([], { tipo: 'cargar', items: [guardado(1, 'preparado')] })
    const a = reducirLista(filas, { tipo: 'marcar', clave: filas[0].clave, estado: 'revisado' })
    expect(reducirLista(a, { tipo: 'descartarCambio', clave: a[0].clave })[0].estado).toBe('preparado')
  })

  it('guardar convierte las filas propuestas en guardadas y deja las excluidas', () => {
    const filas = conPropuesta()
    const sin0 = reducirLista(filas, { tipo: 'alternarIncluir', clave: filas[0].clave })
    const tras = reducirLista(sin0, { tipo: 'guardadas', items: [guardado(1), guardado(2), guardado(3)] })
    expect(tras).toHaveLength(propuestos.length)
    expect(tras[0].itemId).toBeNull()
    expect(tras.slice(1).every((f) => f.itemId !== null && f.estadoGuardado === 'pendiente')).toBe(true)
    expect(itemsAGuardar(tras)).toEqual([])
  })

  it('proponer de nuevo no duplica lo ya guardado', () => {
    const cargadas = reducirLista([], { tipo: 'cargar', items: [guardado(0), guardado(1)] })
    const filas = reducirLista(cargadas, { tipo: 'proponer', items: propuestos })
    expect(filas).toHaveLength(propuestos.length)
    expect(filas.filter((f) => f.itemId !== null)).toHaveLength(2)
  })

  it('cambioGuardado fija el estado del servidor', () => {
    const filas = reducirLista([], { tipo: 'cargar', items: [guardado(0)] })
    const a = reducirLista(filas, { tipo: 'cambioGuardado', item: guardado(0, 'revisado') })
    expect([a[0].estado, a[0].estadoGuardado]).toEqual(['revisado', 'revisado'])
  })
})

describe('API de la lista', () => {
  afterEach(() => vi.unstubAllGlobals())
  const respuesta = (status: number, cuerpo: unknown) => ({ ok: status < 400, status, json: async () => cuerpo })
  const falso = (status: number, cuerpo: unknown = {}) => {
    const f = vi.fn(async () => respuesta(status, cuerpo))
    vi.stubGlobal('fetch', f)
    return f
  }

  it('el guardado no se envía sin confirmar', async () => {
    const f = falso(200, [])
    for (const valor of [false, undefined, 1, 'true'] as unknown[]) {
      await expect(guardarApi('222', propuestos, valor as boolean)).rejects.toBeInstanceOf(ErrorLista)
    }
    expect(f).not.toHaveBeenCalled()
  })

  it('el cambio de estado no se envía sin confirmar', async () => {
    const f = falso(200, {})
    await expect(cambiarEstadoApi('222', 'x', 'pendiente', 'preparado', false)).rejects.toBeInstanceOf(ErrorLista)
    expect(f).not.toHaveBeenCalled()
  })

  it('guardar envía confirmado true, los ítems y ningún tenant_id', async () => {
    const f = falso(200, [])
    await guardarApi('222-IGSS-2023', propuestos, true)
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/eventos/222-IGSS-2023/lista')
    expect(init.method).toBe('POST')
    const cuerpo = JSON.parse(init.body as string)
    expect(cuerpo.confirmado).toBe(true)
    expect(cuerpo.items).toHaveLength(propuestos.length)
    expect(init.body as string).not.toContain('tenant_id')
  })

  it('cambiar estado envía el estado anterior, el nuevo y confirmado true', async () => {
    const f = falso(200, {})
    await cambiarEstadoApi('222', 'abc', 'pendiente', 'preparado', true)
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/eventos/222/lista/abc')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ estado_anterior: 'pendiente', estado_nuevo: 'preparado', confirmado: true })
  })

  it('el 409 muestra el mensaje del diseño', async () => {
    falso(409, { detail: { codigo: 'estado_desactualizado' } })
    const error = await cambiarEstadoApi('222', 'abc', 'pendiente', 'preparado', true).catch((e) => e)
    expect(error).toBeInstanceOf(ErrorLista)
    expect(error.codigo).toBe('estado_desactualizado')
    expect(error.message).toBe(MENSAJE_CONFLICTO)
    expect(MENSAJE_CONFLICTO).toBe('Otro usuario cambió este ítem. Recargue la lista antes de guardar.')
  })

  it('404 y 422 con código dan un mensaje sin texto del documento', async () => {
    falso(422, { detail: { codigo: 'cita_no_valida' } })
    const e422 = await guardarApi('222', propuestos, true).catch((e) => e)
    expect(e422.codigo).toBe('cita_no_valida')
    falso(404, { detail: { codigo: 'item_no_encontrado' } })
    const e404 = await cambiarEstadoApi('222', 'x', 'pendiente', 'preparado', true).catch((e) => e)
    expect(e404.codigo).toBe('item_no_encontrado')
  })

  it('proponer y listar usan las rutas de la API', async () => {
    const f = falso(200, { items: [] })
    await proponerApi('222')
    await listarApi('222')
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe('/api/eventos/222/lista/propuesta')
    expect((f.mock.calls[1] as unknown as [string])[0]).toBe('/api/eventos/222/lista')
  })
})

describe('mostrarCita', () => {
  it('muestra la barra de celda entre el título y el texto como ": "', () => {
    expect(mostrarCita('Período para adquirir los DOCUMENTOS DE LICITACIÓN | A partir de su publicación'))
      .toBe('Período para adquirir los DOCUMENTOS DE LICITACIÓN: A partir de su publicación')
  })

  it('no duplica la puntuación cuando el título ya termina en ella', () => {
    expect(mostrarCita('Apertura de PLICAS. | Después de concluido el período'))
      .toBe('Apertura de PLICAS. Después de concluido el período')
  })

  it('deja intacto el texto sin barras de celda y las barras dentro de una palabra', () => {
    expect(mostrarCita('El código AB|12 corresponde')).toBe('El código AB|12 corresponde')
    expect(mostrarCita('Texto sin tabla.')).toBe('Texto sin tabla.')
  })
})
