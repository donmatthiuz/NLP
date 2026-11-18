import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Resultado } from './componentes/Resultado'
import { EJEMPLOS } from './ejemplos'

const html = (id: string) =>
  renderToStaticMarkup(createElement(Resultado, { respuesta: EJEMPLOS.find((e) => e.id === id)!.respuesta, pregunta: 'p', alEscribirAclaracion: () => {} }))

describe('rótulo de la revisión humana', () => {
  it('en revisión el rótulo está en el h2 y no se repite en la banda', () => {
    const h = html('comparacion')
    expect(h).not.toContain('<strong>Requiere revisión humana.</strong>')
    expect((h.match(/Requiere revisión humana/g) ?? []).length).toBe(1)
  })
})
