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

describe('aviso de afirmaciones descartadas', () => {
  const conAviso = (coverage_status: 'parcial' | 'sin_faltantes_detectados') => {
    const base = EJEMPLOS.find((e) => e.id === 'respuesta')!.respuesta
    return renderToStaticMarkup(createElement(Resultado, {
      respuesta: { ...base, coverage_status, warnings: ['afirmaciones_descartadas: 2'] }, pregunta: 'p', alEscribirAclaracion: () => {} }))
  }
  it('tiene texto propio y no habla de páginas sin indexar', () => {
    const h = conAviso('sin_faltantes_detectados')
    expect(h).toContain('Se omitieron afirmaciones que no pasaron la validación de citas')
    expect(h).not.toContain('Aviso del sistema')
    expect(h).not.toContain('sin indexar')
    expect(h).not.toContain('no están indexados')
  })
})

describe('avisos de fechas', () => {
  const conAvisos = (warnings: string[]) => {
    const base = EJEMPLOS.find((e) => e.id === 'respuesta')!.respuesta
    return renderToStaticMarkup(createElement(Resultado, {
      respuesta: { ...base, warnings }, pregunta: 'p', alEscribirAclaracion: () => {} }))
  }
  it('fechas_no_verificadas y fecha_ambigua tienen rótulo propio', () => {
    const h = conAvisos(['fechas_no_verificadas: 3', 'fecha_ambigua: apertura_plicas, recepcion_ofertas'])
    expect(h).toContain('<strong>Fechas sin verificar</strong>')
    expect(h).toContain('<strong>Fecha ambigua: requiere revisión</strong>')
    expect(h).not.toContain('Aviso del sistema')
  })
  it('candidatas_sin_verificar ya no existe', () => {
    expect(conAvisos(['candidatas_sin_verificar: 2'])).toContain('Aviso del sistema')
  })
})
