import { afterEach, describe, expect, it, vi } from 'vitest'
import { documentosApi, ErrorConsulta } from './api'
import { EJEMPLO_DOCUMENTOS } from './ejemplos'
import { faltantesDe, resumenCobertura, rotuloEstadoDocumento, rotuloTipoDocumento, textoPaginas } from './cobertura'
import type { DocumentoEvento } from './tipos'

const [bases, modificacion] = EJEMPLO_DOCUMENTOS.documentos

const completo = (cambios: Partial<DocumentoEvento> = {}): DocumentoEvento => ({ ...bases, ...cambios })

describe('panel de cobertura del evento', () => {
  it('un documento completo no tiene faltantes', () => {
    expect(bases.estado).toBe('completo')
    expect(faltantesDe(bases)).toEqual([])
  })

  it('la modificación del 222 destaca la página sin indexar, el estado y el anexo que no está cargado', () => {
    expect(faltantesDe(modificacion)).toEqual([
      'Páginas sin indexar: 4',
      'Estado: requiere revisión',
      'Hay páginas incompletas o ilegibles',
      'Menciona un anexo de 11 hojas que no está cargado',
    ])
  })

  it('un estado distinto de completo es un faltante aunque no haya páginas ni advertencias', () => {
    expect(faltantesDe(completo({ estado: 'incompleto' }))).toEqual(['Estado: incompleto'])
  })

  it('el resumen cuenta documentos y los que tienen faltantes', () => {
    expect(resumenCobertura(EJEMPLO_DOCUMENTOS.documentos)).toEqual({
      total: 2, conFaltantes: 1, texto: '2 documentos, 1 con información faltante',
    })
    expect(resumenCobertura([bases])).toEqual({ total: 1, conFaltantes: 0, texto: '1 documento, sin información faltante' })
    expect(resumenCobertura([])).toEqual({ total: 0, conFaltantes: 0, texto: 'No hay documentos cargados para este evento' })
  })

  it('rótulos de tipo, estado y páginas', () => {
    expect(rotuloTipoDocumento('modificacion')).toBe('Modificación')
    expect(rotuloTipoDocumento('otro')).toBe('otro')
    expect(rotuloEstadoDocumento('requiere_revision')).toBe('Requiere revisión')
    expect(textoPaginas(bases)).toBe('35 páginas, todas indexadas')
    expect(textoPaginas(modificacion)).toBe('4 páginas, 1 sin indexar (p. 4)')
    expect(textoPaginas(completo({ paginas_total: null }))).toBe('Páginas no informadas')
  })
})

describe('documentosApi', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('pide la ruta del evento sin enviar tenant_id', async () => {
    const fetchFalso = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => EJEMPLO_DOCUMENTOS })
    vi.stubGlobal('fetch', fetchFalso)
    expect(await documentosApi('222-IGSS-2023')).toEqual(EJEMPLO_DOCUMENTOS)
    expect(fetchFalso).toHaveBeenCalledWith('/api/eventos/222-IGSS-2023/documentos')
  })

  it('un error HTTP o de red es ErrorConsulta con un mensaje sin detalle', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }))
    await expect(documentosApi('x')).rejects.toBeInstanceOf(ErrorConsulta)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('red')))
    await expect(documentosApi('x')).rejects.toThrow('La API no respondió')
  })
})
