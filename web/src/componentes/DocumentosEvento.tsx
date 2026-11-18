import { useEffect, useState } from 'react'
import { ErrorConsulta, ErrorNoAutenticado, documentosApi } from '../api'
import { advertenciasDe, faltantesDe, resumenCobertura, rotuloEstadoDocumento, rotuloTipoDocumento, textoPaginas } from '../cobertura'
import { EJEMPLO_DOCUMENTOS } from '../ejemplos'
import type { DocumentoEvento, DocumentosEvento as Documentos } from '../tipos'

export type Carga = { tipo: 'cargando' } | { tipo: 'error'; motivo: string } | { tipo: 'listo'; datos: Documentos }

// La carga vive en App para que las citas de las fuentes y de la lista conozcan el tipo de cada documento.
export function useDocumentosEvento(eventoId: string, modoEjemplos: boolean, habilitado = true): Carga {
  const [carga, setCarga] = useState<Carga>({ tipo: 'cargando' })

  useEffect(() => {
    if (modoEjemplos) { setCarga({ tipo: 'listo', datos: EJEMPLO_DOCUMENTOS }); return }
    if (!habilitado) return
    let activo = true
    setCarga({ tipo: 'cargando' })
    documentosApi(eventoId)
      .then((datos) => { if (activo) setCarga({ tipo: 'listo', datos }) })
      .catch((e) => { if (activo && !(e instanceof ErrorNoAutenticado)) setCarga({ tipo: 'error', motivo: e instanceof ErrorConsulta ? e.message : 'Error inesperado' }) })
    return () => { activo = false }
  }, [eventoId, modoEjemplos, habilitado])
  return carga
}

export function ListaDocumentos({ documentos }: { documentos: DocumentoEvento[] }) {
  return (
    <ul className="documentos__lista">
      {documentos.map((d) => {
        const faltantes = advertenciasDe(d)
        return (
          <li key={d.doc_id} className="documento" data-faltantes={faltantesDe(d).length > 0}>
            <p className="documento__titulo">
              <span className="etiqueta">{rotuloTipoDocumento(d.tipo_documento)}</span>
              {d.version_oficial ? <span>{d.version_oficial}</span> : <span className="etiqueta etiqueta--suave">Versión oficial no indicada</span>}
              <span className="etiqueta etiqueta--suave">v{d.version_ingesta}</span>
            </p>
            <p className="documento__id"><code className="mono">{d.doc_id}</code></p>
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
  )
}

export function DocumentosEvento({ carga }: { carga: Carga }) {
  const resumen = carga.tipo === 'listo' ? resumenCobertura(carga.datos.documentos) : null
  return (
    <section className="documentos" aria-labelledby="titulo-documentos">
      <h2 id="titulo-documentos">Documentos del evento</h2>
      {carga.tipo === 'cargando' && <p className="ayuda" aria-busy="true">Cargando documentos…</p>}
      {carga.tipo === 'error' && <p className="ayuda" role="alert">No se pudieron cargar los documentos. {carga.motivo}</p>}
      {resumen && (
        <p className="documentos__resumen" data-faltantes={resumen.conFaltantes > 0}>{resumen.texto}</p>
      )}
      {carga.tipo === 'listo' && carga.datos.documentos.length > 0 && <ListaDocumentos documentos={carga.datos.documentos} />}
    </section>
  )
}
