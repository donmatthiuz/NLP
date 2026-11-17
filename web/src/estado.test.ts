import { describe, expect, it } from 'vitest'
import { EJEMPLOS } from './ejemplos'
import { agruparPorDocumento, alAclarar, esHttps, estadoDe, motivoRevision } from './estado'

const estadoEjemplo = (id: string) => estadoDe(EJEMPLOS.find((e) => e.id === id)!.respuesta)

describe('estadoDe con los cinco ejemplos', () => {
  it('respuesta', () => expect(estadoEjemplo('respuesta')).toBe('respuesta'))
  it('abstención', () => expect(estadoEjemplo('abstencion')).toBe('abstencion'))
  it('revisión humana', () => expect(estadoEjemplo('comparacion')).toBe('revision'))
  it('aclaración', () => expect(estadoEjemplo('aclaracion')).toBe('aclaracion'))
  it('cobertura parcial citando una modificación escala a revisión', () => expect(estadoEjemplo('cobertura_parcial')).toBe('revision'))
})

describe('precedencia', () => {
  it('aclaración gana a abstención y revisión', () =>
    expect(estadoDe({ needs_clarification: true, abstained: true, needs_human_review: true })).toBe('aclaracion'))
  it('abstención gana a revisión', () =>
    expect(estadoDe({ needs_clarification: false, abstained: true, needs_human_review: true })).toBe('abstencion'))
})

describe('motivo de la banda de revisión', () => {
  const comparacion = EJEMPLOS.find((e) => e.id === 'comparacion')!.respuesta
  it('sin revisión no hay banda', () =>
    expect(motivoRevision({ needs_human_review: false, sources: comparacion.sources })).toBeNull())
  it('con fuentes de dos documentos dice que las fuentes difieren', () =>
    expect(motivoRevision(comparacion)).toContain('Las fuentes difieren'))
  it('una abstención sin fuentes no dice que las fuentes difieren', () => {
    const m = motivoRevision({ needs_human_review: true, sources: [] })
    expect(m).not.toBeNull()
    expect(m).not.toContain('Las fuentes difieren')
  })
  it('fuentes de un solo documento tampoco', () =>
    expect(motivoRevision({ needs_human_review: true, sources: [comparacion.sources[0]] })).not.toContain('Las fuentes difieren'))
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

describe('aclaración sin memoria', () => {
  it('conserva la pregunta y deja el cursor al final', () => {
    const r = alAclarar('  ¿Cuál es la fecha?  ')
    expect(r.texto).toBe('  ¿Cuál es la fecha?  ')
    expect(r.cursor).toBe(r.texto.length)
  })
})
