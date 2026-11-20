import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ErrorNoAutenticado, MENSAJE_CREDENCIALES, MENSAJE_ROL, cerrarSesionApi, consultarApi, guardarApi,
  iniciarSesionApi, obtenerSesionApi, alPerderSesion, proponerApi,
} from './api'
import { InicioSesion } from './componentes/InicioSesion'
import { ZonaFuentes } from './componentes/Fuentes'
import { FilaItem, ListaVerificacion, ofreceRecargar } from './componentes/ListaVerificacion'
import { EJEMPLOS, EJEMPLO_PROPUESTA } from './ejemplos'
import { MENSAJE_SESION_TERMINADA, textoSesion } from './estado'

const respuesta = (estado: number, cuerpo?: unknown) =>
  new Response(cuerpo === undefined ? null : JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } })
const falsoFetch = (...rs: Response[]) => {
  const f = vi.fn()
  rs.forEach((r) => f.mockResolvedValueOnce(r))
  vi.stubGlobal('fetch', f)
  return f
}
afterEach(() => { vi.unstubAllGlobals(); alPerderSesion(null) })

describe('sesión', () => {
  it('GET /api/sesion con 200 devuelve usuario, empresa y rol', async () => {
    const f = falsoFetch(respuesta(200, { usuario: 'ana', tenant_id: 'empresa_demo', rol: 'analista' }))
    expect(await obtenerSesionApi()).toEqual({ usuario: 'ana', tenant_id: 'empresa_demo', rol: 'analista' })
    expect(f.mock.calls[0][0]).toBe('/api/sesion')
  })

  it('GET /api/sesion con 401 devuelve null (pantalla de inicio de sesión)', async () => {
    falsoFetch(respuesta(401, { detail: { codigo: 'sin_sesion' } }))
    expect(await obtenerSesionApi()).toBeNull()
  })

  it('POST /api/sesion envía solo usuario y contraseña; 401 da el mensaje genérico', async () => {
    const f = falsoFetch(respuesta(204), respuesta(401, { detail: { codigo: 'credenciales_invalidas' } }))
    await iniciarSesionApi('ana', 'secreta')
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/sesion')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ usuario: 'ana', contrasena: 'secreta' })
    await expect(iniciarSesionApi('ana', 'mala')).rejects.toThrow(MENSAJE_CREDENCIALES)
  })

  it('no guarda la contraseña en ningún almacenamiento ni lee la cookie', async () => {
    const almacen = { setItem: vi.fn(), getItem: vi.fn() }
    vi.stubGlobal('localStorage', almacen)
    vi.stubGlobal('sessionStorage', almacen)
    falsoFetch(respuesta(204))
    await iniciarSesionApi('ana', 'secreta')
    expect(almacen.setItem).not.toHaveBeenCalled()
  })

  it('DELETE /api/sesion cierra la sesión', async () => {
    const f = falsoFetch(respuesta(204))
    await cerrarSesionApi()
    expect(f.mock.calls[0][0]).toBe('/api/sesion')
    expect(f.mock.calls[0][1].method).toBe('DELETE')
  })

  it('un 401 a mitad de uso avisa a la aplicación y lanza ErrorNoAutenticado', async () => {
    const aviso = vi.fn()
    alPerderSesion(aviso)
    falsoFetch(respuesta(401, { detail: { codigo: 'sin_sesion' } }), respuesta(401, {}))
    await expect(consultarApi('222-IGSS-2023', 'hola')).rejects.toBeInstanceOf(ErrorNoAutenticado)
    await expect(proponerApi('222-IGSS-2023')).rejects.toBeInstanceOf(ErrorNoAutenticado)
    expect(aviso).toHaveBeenCalledTimes(2)
  })

  it('un 403 en la lista da el mensaje de rol, no una falla genérica', async () => {
    falsoFetch(respuesta(403, { detail: { codigo: 'rol_no_permitido' } }))
    await expect(guardarApi('222-IGSS-2023', [], true)).rejects.toThrow(MENSAJE_ROL)
    expect(MENSAJE_ROL).toBe('Su rol no permite modificar la lista')
  })

  it('ya no lee la cabecera X-LiciGT-Autenticacion', async () => {
    falsoFetch(respuesta(200, EJEMPLOS[0].respuesta))
    const r = await consultarApi('222-IGSS-2023', 'hola')
    expect(r).not.toHaveProperty('sinAutenticacion')
  })
})

describe('pantalla de inicio de sesión', () => {
  const html = (error: string | null = null) =>
    renderToStaticMarkup(createElement(InicioSesion, { error, enviando: false, alEntrar: () => {} }))

  it('trae usuario y contraseña con label y el botón', () => {
    const h = html()
    expect(h).toMatch(/<label[^>]*for="[^"]+"[^>]*>Usuario<\/label>/)
    expect(h).toMatch(/<label[^>]*for="[^"]+"[^>]*>Contraseña<\/label>/)
    expect(h).toContain('type="password"')
    expect(h).toContain('autoComplete="current-password"')
    expect(h).toContain('Iniciar sesión')
  })

  it('muestra el error genérico en un rol alert', () => {
    expect(html(MENSAJE_CREDENCIALES)).toMatch(/role="alert"[^>]*>[^<]*Usuario o contraseña no válidos/)
    expect(html()).not.toContain('role="alert"')
  })
})

describe('original del PDF en cada fuente', () => {
  const fuentes = EJEMPLOS.find((e) => e.id === 'respuesta')!.respuesta.sources
  const zona = (eventoId?: string) =>
    renderToStaticMarkup(createElement(ZonaFuentes, { fuentes, abstencion: false, conflicto: false, eventoId }))

  it('con evento, el enlace lleva el doc_id y la página de la fuente y se abre en pestaña nueva', () => {
    const h = zona('222-IGSS-2023')
    const f = fuentes[0]
    expect(h).toContain(`href="/api/eventos/222-IGSS-2023/documentos/${f.doc_id}/original?p=${f.page}#page=${f.page}"`)
    expect(h).toContain(`Ver copia archivada, p. ${f.page}`)
    expect(h).toContain('target="_blank"')
    expect(h.match(/rel="noopener"/g)?.length).toBe(fuentes.length)
  })

  it('con una fuente https hay dos enlaces con nombres inequívocos', () => {
    const f = { ...fuentes[0], source: 'https://igssgt.org/doc.pdf' }
    const h = renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: [f], abstencion: false, conflicto: false, eventoId: 'E1' }))
    expect(h).toMatch(/<a [^>]*href="\/api\/eventos\/E1[^"]*"[^>]*>Ver copia archivada, p\. /)
    expect(h).toMatch(/<a [^>]*href="https:\/\/igssgt\.org\/doc\.pdf#page=\d+"[^>]*>Publicación en igssgt\.org/)
    expect(h).not.toContain('Abrir documento original')
  })

  it('en modo ejemplos (sin evento) el enlace no aparece', () => {
    expect(zona()).not.toContain('Ver copia archivada')
    expect(zona()).not.toContain('/original')
  })

  it('codifica el doc_id de la fuente en la ruta', () => {
    const raro = [{ ...fuentes[0], doc_id: 'a/b?c' }]
    const h = renderToStaticMarkup(createElement(ZonaFuentes, { fuentes: raro, abstencion: false, conflicto: false, eventoId: 'E1' }))
    expect(h).toContain('/api/eventos/E1/documentos/a%2Fb%3Fc/original?p=')
  })
})

describe('cabecera y errores de sesión', () => {
  it('el texto de sesión va en un solo span', () => {
    expect(textoSesion({ usuario: 'ana', tenant_id: 'empresa_demo', rol: 'analista' })).toBe('ana · empresa_demo · rol analista')
  })
  it('el 401 a mitad de uso deja el mensaje para el role alert', () => {
    expect(MENSAJE_SESION_TERMINADA).toBe('La sesión terminó. Inicie sesión de nuevo.')
    expect(new ErrorNoAutenticado().message).toBe(MENSAJE_SESION_TERMINADA)
  })
  it('no ofrece recargar cuando el aviso es de rol', () => {
    expect(ofreceRecargar('rol_no_permitido')).toBe(false)
    expect(ofreceRecargar('http_500')).toBe(true)
  })
})

describe('lista con rol lector', () => {
  const lista = (soloLectura: boolean) => {
    vi.stubGlobal('window', { location: { search: '' } })
    return renderToStaticMarkup(createElement(ListaVerificacion, { eventoId: 'E', modoEjemplos: true, soloLectura }))
  }

  it('deshabilita proponer y guardar y explica por qué', () => {
    const h = lista(true)
    expect(h).toMatch(/<button[^>]*disabled=""[^>]*>Proponer lista/)
    expect(h).toMatch(/<button[^>]*disabled=""[^>]*>Guardar 0/)
    expect(h).toContain('Su rol no permite modificar la lista')
  })

  it('los radios del lector se deshabilitan con el fieldset descrito por la explicación', () => {
    const fila = { clave: 'c', item: EJEMPLO_PROPUESTA.items[0], itemId: 'i1', estado: 'pendiente' as const, estadoGuardado: null, incluir: true }
    const h = renderToStaticMarkup(createElement(FilaItem, {
      fila, soloLectura: true, idExplicacion: 'expl', alIncluir: () => {}, alMarcar: () => {}, alGuardarCambio: () => {}, alDescartar: () => {},
    }))
    expect(h).toMatch(/<fieldset[^>]*disabled=""[^>]*aria-describedby="expl"|<fieldset[^>]*aria-describedby="expl"[^>]*disabled=""/)
    // Radix no se entera del fieldset: el RadioGroup recibe disabled y cada radio lo refleja.
    const radios = h.match(/<button[^>]*role="radio"[^>]*>/g) ?? []
    expect(radios).toHaveLength(3)
    for (const r of radios) expect(r).toMatch(/disabled=""/)
    expect(h).toMatch(/role="radiogroup"[^>]*data-disabled=""|data-disabled=""[^>]*role="radiogroup"/)
  })

  it('la casilla Incluir del lector también va deshabilitada', () => {
    const fila = { clave: 'c', item: EJEMPLO_PROPUESTA.items[0], itemId: null, estado: 'pendiente' as const, estadoGuardado: null, incluir: true }
    const html = (soloLectura: boolean) => renderToStaticMarkup(createElement(FilaItem, {
      fila, soloLectura, alIncluir: () => {}, alMarcar: () => {}, alGuardarCambio: () => {}, alDescartar: () => {},
    }))
    expect(html(true)).toMatch(/<button(?=[^>]*role="checkbox")(?=[^>]*disabled="")[^>]*>/)
    expect(html(false)).not.toMatch(/<button(?=[^>]*role="checkbox")(?=[^>]*disabled="")[^>]*>/)
  })

  it('con otro rol no los deshabilita por rol ni muestra la explicación', () => {
    const h = lista(false)
    expect(h).not.toMatch(/<button[^>]*disabled=""[^>]*>Proponer lista/)
    expect(h).not.toContain('Su rol no permite modificar la lista')
  })
})
