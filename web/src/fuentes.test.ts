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
    expect(html).toMatch(/<blockquote[^>]*lang="es"[^>]*id="/)
    expect(html).toMatch(/<blockquote[^>]*>31 de julio de 2023<\/blockquote>/)
    expect(html).toMatch(/<span data-slot="badge" data-variant="suave"[^>]*>Recepción de ofertas<\/span>/)
  })

  it('en un requisito la cita es la descripción y no hay etiqueta de actividad', () => {
    expect(partesItem(EJEMPLO_PROPUESTA.items[0])).toEqual({ etiqueta: null, cita: EJEMPLO_PROPUESTA.items[0].fuentes[0].cita })
    expect(partesItem(EJEMPLO_PROPUESTA.items[2])).toEqual({ etiqueta: 'Recepción de ofertas', cita: '31 de julio de 2023' })
  })

  it('la casilla Incluir se anuncia con su ítem', () => {
    const html = itemHtml(2, tipos)
    const id = /<blockquote[^>]*id="([^"]+)"/.exec(html)![1]
    // Radix pinta la casilla como <button role="checkbox">; el aria-describedby debe llegar a ese mismo elemento.
    expect(html).toMatch(new RegExp(`<button(?=[^>]*role="checkbox")(?=[^>]*aria-describedby="${id}")[^>]*>`))
    expect((html.match(/role="checkbox"/g) ?? []).length).toBe(1)
  })
})

describe('página del PDF y página impresa', () => {
  const base = comparacion.sources[0]
  const tarjeta = (f: typeof base, eventoId?: string) =>
    renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: [f], abstencion: false, conflicto: false, eventoId }))

  it('sin printed_page muestra solo la página del PDF', () => {
    const h = tarjeta({ ...base, page: 8, page_end: null })
    expect(h).toContain('p. 8 del PDF')
    expect(h).not.toContain('impresa')
  })

  it('con printed_page agrega la impresa y el enlace sigue en la página del PDF', () => {
    const h = tarjeta({ ...base, page: 8, page_end: null, printed_page: 6 }, 'E1')
    expect(h).toContain('p. 8 del PDF (impresa 6)')
    expect(h).toContain('#page=8"')
    expect(h).toContain('Ver copia archivada, p. 8 del PDF')
    expect(h).not.toContain('#page=6')
  })

  it('un rango dice pp. y el ítem de la lista usa el mismo texto', () => {
    const f = { ...base, page: 16, page_end: 17, printed_page: 14 }
    expect(tarjeta(f)).toContain('pp. 16–17 del PDF (impresa 14)')
    const item = { ...EJEMPLO_PROPUESTA.items[0], fuentes: [f] }
    const lista = renderToStaticMarkup(createElement(FilaItem, {
      fila: { clave: 'x', item, itemId: null, estado: 'pendiente', estadoGuardado: null, incluir: true },
      alIncluir: () => {}, alMarcar: () => {}, alGuardarCambio: () => {}, alDescartar: () => {},
    }))
    expect(lista).toContain('pp. 16–17 del PDF (impresa 14)')
  })
})

describe('enlaces que abren en la página citada', () => {
  const base = comparacion.sources[0]
  const tarjeta = (f: typeof base, eventoId?: string) =>
    renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: [f], abstencion: false, conflicto: false, eventoId }))
  const hrefs = (h: string) => [...h.matchAll(/href="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, '&'))

  it('la copia archivada lleva una URL única por página y el fragmento de la página física', () => {
    const h = tarjeta({ ...base, page: 20, page_end: null, printed_page: 19 }, 'E1')
    expect(hrefs(h)).toContain('/api/eventos/E1/documentos/' + base.doc_id + '/original?p=20#page=20')
    const otra = tarjeta({ ...base, page: 24, page_end: null }, 'E1')
    expect(otra).toContain('/original?p=24#page=24')
  })

  it('el enlace externo a un PDF directo conserva #page=N con la página física', () => {
    const h = tarjeta({ ...base, page: 20, page_end: null, printed_page: 19, source: 'https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf' }, 'E1')
    expect(hrefs(h)).toContain('https://www.igssgt.org/wp-content/uploads/2026/10/222-IGSS-2023.pdf#page=20')
    expect(h).toContain('Publicación en igssgt.org, p. 20 del PDF')
  })

  it('si la publicación no es un PDF directo no promete la página', () => {
    const h = tarjeta({ ...base, page: 20, page_end: null, source: 'https://www.igssgt.org/proveedores/?y=2023' }, 'E1')
    expect(hrefs(h)).toContain('https://www.igssgt.org/proveedores/?y=2023')
    expect(h).toContain('Publicación en igssgt.org (página sin enlace directo)')
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
