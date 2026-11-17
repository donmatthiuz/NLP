import { useEffect, useState } from 'react'
import { ErrorConsulta, documentosApi } from '../api'
import { faltantesDe, resumenCobertura, rotuloEstadoDocumento, rotuloTipoDocumento, textoPaginas } from '../cobertura'
import { EJEMPLO_DOCUMENTOS } from '../ejemplos'
import type { DocumentosEvento as Documentos } from '../tipos'

type Carga = { tipo: 'cargando' } | { tipo: 'error'; motivo: string } | { tipo: 'listo'; datos: Documentos }

export function DocumentosEvento({ eventoId, modoEjemplos }: { eventoId: string; modoEjemplos: boolean }) {
  const [carga, setCarga] = useState<Carga>({ tipo: 'cargando' })

  useEffect(() => {
    if (modoEjemplos) { setCarga({ tipo: 'listo', datos: EJEMPLO_DOCUMENTOS }); return }
    let activo = true
    setCarga({ tipo: 'cargando' })
    documentosApi(eventoId)
      .then((datos) => { if (activo) setCarga({ tipo: 'listo', datos }) })
      .catch((e) => { if (activo) setCarga({ tipo: 'error', motivo: e instanceof ErrorConsulta ? e.message : 'Error inesperado' }) })
    return () => { activo = false }
  }, [eventoId, modoEjemplos])

  const resumen = carga.tipo === 'listo' ? resumenCobertura(carga.datos.documentos) : null
  return (
    <section className="documentos" aria-labelledby="titulo-documentos">
      <h2 id="titulo-documentos">Documentos del evento</h2>
      {carga.tipo === 'cargando' && <p className="ayuda" aria-busy="true">Cargando documentos…</p>}
      {carga.tipo === 'error' && <p className="ayuda" role="alert">No se pudieron cargar los documentos. {carga.motivo}</p>}
      {resumen && (
        <p className="documentos__resumen" data-faltantes={resumen.conFaltantes > 0}>{resumen.texto}</p>
      )}
      {carga.tipo === 'listo' && carga.datos.documentos.length > 0 && (
        <ul className="documentos__lista">
          {carga.datos.documentos.map((d) => {
            const faltantes = faltantesDe(d)
            return (
              <li key={d.doc_id} className="documento" data-faltantes={faltantes.length > 0}>
                <p className="documento__titulo">
                  <span className="etiqueta">{rotuloTipoDocumento(d.tipo_documento)}</span>
                  <span>{d.version_oficial ?? 'Versión oficial no indicada'}</span>
                  <span className="etiqueta etiqueta--suave">v{d.version_ingesta}</span>
                </p>
                <p className="documento__datos">
                  {textoPaginas(d)}; estado: {rotuloEstadoDocumento(d.estado).toLowerCase()}
                </p>
                {faltantes.length > 0 && (
                  <div className="documento__faltantes">
                    <p className="etiqueta etiqueta--aviso">Falta información</p>
                    <ul>{faltantes.map((f) => <li key={f}>{f}</li>)}</ul>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
