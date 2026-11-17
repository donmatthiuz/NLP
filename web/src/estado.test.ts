import { describe, expect, it } from 'vitest'
import { EJEMPLOS } from './ejemplos'
import { agruparPorDocumento, esHttps, estadoDe } from './estado'

const estadoEjemplo = (id: string) => estadoDe(EJEMPLOS.find((e) => e.id === id)!.respuesta)

describe('estadoDe con los cinco ejemplos', () => {
  it('respuesta', () => expect(estadoEjemplo('respuesta')).toBe('respuesta'))
  it('abstención', () => expect(estadoEjemplo('abstencion')).toBe('abstencion'))
  it('revisión humana', () => expect(estadoEjemplo('comparacion')).toBe('revision'))
  it('aclaración', () => expect(estadoEjemplo('aclaracion')).toBe('aclaracion'))
  it('cobertura parcial sigue siendo respuesta', () => expect(estadoEjemplo('cobertura_parcial')).toBe('respuesta'))
})

describe('precedencia', () => {
  it('aclaración gana a abstención y revisión', () =>
    expect(estadoDe({ needs_clarification: true, abstained: true, needs_human_review: true })).toBe('aclaracion'))
  it('abstención gana a revisión', () =>
    expect(estadoDe({ needs_clarification: false, abstained: true, needs_human_review: true })).toBe('abstencion'))
})

describe('auxiliares', () => {
  it('agrupa las fuentes por documento en orden de aparición', () => {
    const g = agruparPorDocumento(EJEMPLOS.find((e) => e.id === 'comparacion')!.respuesta.sources)
    expect(g).toHaveLength(2)
    expect(g[0].doc_id).not.toBe(g[1].doc_id)
  })
  it('solo https es enlace', () => {
    expect(esHttps('https://www.igssgt.org/a.pdf')).toBe(true)
    expect(esHttps('http://x.org/a.pdf')).toBe(false)
    expect(esHttps('javascript:alert(1)')).toBe(false)
    expect(esHttps('03791a3471c04c0f9cc260814564756e')).toBe(false)
  })
})
