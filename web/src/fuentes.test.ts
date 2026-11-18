import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { FilaItem } from './componentes/ListaVerificacion'
import { ZonaFuentes } from './componentes/Fuentes'
import { EJEMPLOS, EJEMPLO_DOCUMENTOS, EJEMPLO_PROPUESTA } from './ejemplos'
import { mapaTipos } from './cobertura'
import { partesItem } from './lista'
import type { FilaLista } from './lista'

const comparacion = EJEMPLOS.find((e) => e.id === 'comparacion')!.respuesta
const tipos = mapaTipos(EJEMPLO_DOCUMENTOS.documentos)
const zona = (t?: Record<string, string>) =>
  renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: comparacion.sources, abstencion: false, conflicto: true, tipos: t }))

describe('fuentes con el tipo del documento', () => {
  it('con el mapa, cada columna y cada tarjeta nombran el tipo antes del hash', () => {
    const html = zona(tipos)
    expect(html).toContain('Bases · 03791a3471c04c0f9cc260814564756e')
    expect(html).toContain('Modificación · d41480e5b0ce4c16bf18f66225ada2dc')
    expect((html.match(/Bases · 03791a/g) ?? []).length).toBeGreaterThanOrEqual(2)
  })

  it('sin el mapa muestra solo el hash, como antes', () => {
    const html = zona()
    expect(html).not.toContain('Bases ·')
    expect(html).toContain('03791a3471c04c0f9cc260814564756e')
  })
})

const fila = (i: number): FilaLista => {
  const item = EJEMPLO_PROPUESTA.items[i]
  return { clave: `c${i}`, item, itemId: null, estado: 'pendiente', estadoGuardado: null, incluir: true }
}
const itemHtml = (i: number, t?: Record<string, string>) =>
  renderToStaticMarkup(createElement(FilaItem, {
    fila: fila(i), tipos: t, alIncluir: () => {}, alMarcar: () => {}, alGuardarCambio: () => {}, alDescartar: () => {},
  }))

describe('ítems de la lista', () => {
  it('el origen lleva el tipo antes del hash con el mapa y solo el hash sin él', () => {
    expect(itemHtml(2, tipos)).toContain('Bases · 03791a3471c04c0f9cc260814564756e')
    expect(itemHtml(3, tipos)).toContain('Modificación · d41480e5b0ce4c16bf18f66225ada2dc')
    expect(itemHtml(3)).not.toContain('Modificación ·')
  })

  it('la cita del ítem es la cita de su fuente y la etiqueta de la actividad queda fuera', () => {
    const html = itemHtml(2, tipos)
    expect(html).toContain('<blockquote class="cita" lang="es" id=')
    expect(html).toMatch(/<blockquote[^>]*>31 de julio de 2023<\/blockquote>/)
    expect(html).toMatch(/class="etiqueta etiqueta--suave">Recepción de ofertas<\/span>/)
  })

  it('en un requisito la cita es la descripción y no hay etiqueta de actividad', () => {
    expect(partesItem(EJEMPLO_PROPUESTA.items[0])).toEqual({ etiqueta: null, cita: EJEMPLO_PROPUESTA.items[0].fuentes[0].cita })
    expect(partesItem(EJEMPLO_PROPUESTA.items[2])).toEqual({ etiqueta: 'Recepción de ofertas', cita: '31 de julio de 2023' })
  })

  it('la casilla Incluir se anuncia con su ítem', () => {
    const html = itemHtml(2, tipos)
    const id = /<blockquote[^>]*id="([^"]+)"/.exec(html)![1]
    expect(html).toMatch(new RegExp(`<input type="checkbox"[^>]*aria-describedby="${id}"`))
  })
})

describe('misma cita en las dos vistas', () => {
  it('una cita de tabla se ve igual en la tarjeta de fuente y en el ítem', () => {
    const f = { ...comparacion.sources[0], cita: 'Apertura de PLICAS | Después del período' }
    const tarjeta = renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: [f], abstencion: false, conflicto: false }))
    const item = { ...EJEMPLO_PROPUESTA.items[0], descripcion: f.cita, fuentes: [f] }
    const lista = renderToStaticMarkup(createElement(FilaItem, {
      fila: { clave: 'x', item, itemId: null, estado: 'pendiente', estadoGuardado: null, incluir: true },
      alIncluir: () => {}, alMarcar: () => {}, alGuardarCambio: () => {}, alDescartar: () => {},
    }))
    const frase = 'Apertura de PLICAS: Después del período'
    expect(tarjeta).toContain(frase)
    expect(lista).toContain(frase)
  })
})
