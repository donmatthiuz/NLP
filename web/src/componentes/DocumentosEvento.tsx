import { useEffect, useState } from 'react'
import { ErrorConsulta, ErrorNoAutenticado, documentosApi } from '../api'
import { advertenciasDe, faltantesDe, resumenCobertura, rotuloEstadoDocumento, rotuloTipoDocumento, textoPaginas } from '../cobertura'
import { EJEMPLO_DOCUMENTOS } from '../ejemplos'
import type { DocumentoEvento, DocumentosEvento as Documentos } from '../tipos'
import { Alert } from './ui/alert'
import { Badge } from './ui/badge'
import { Card } from './ui/card'

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
    <ul className="grid gap-3">
      {documentos.map((d) => {
        const faltantes = advertenciasDe(d)
        return (
          <Card asChild key={d.doc_id}
            className="@container gap-2 px-4 py-3 data-[faltantes=true]:border-2 data-[faltantes=true]:border-estado-revision data-[faltantes=true]:bg-estado-revision-fondo">
            <li data-faltantes={faltantesDe(d).length > 0}>
              <p className="flex flex-wrap items-center gap-2 font-semibold">
                <Badge>{rotuloTipoDocumento(d.tipo_documento)}</Badge>
                {d.version_oficial ? <span>{d.version_oficial}</span> : <Badge variant="suave">Versión oficial no indicada</Badge>}
                <Badge variant="suave">v{d.version_ingesta}</Badge>
              </p>
              <dl className="grid min-w-0 gap-x-4 gap-y-2 text-sm @md:grid-cols-2">
                <div className="flex min-w-0 flex-wrap content-start gap-x-1">
                  <dt className="sr-only">Documento</dt>
                  <dd className="min-w-0 wrap-anywhere"><code className="font-mono text-sm wrap-anywhere">{d.doc_id}</code></dd>
                </div>
                <div className="flex min-w-0 flex-wrap content-start gap-x-1">
                  <dt className="sr-only">Páginas y estado</dt>
                  <dd className="min-w-0 wrap-anywhere">{textoPaginas(d)}; estado: {rotuloEstadoDocumento(d.estado).toLowerCase()}</dd>
                </div>
              </dl>
              {faltantes.length > 0 && (
                <div className="grid justify-items-start gap-2">
                  <Badge variant="aviso">Falta información</Badge>
                  <ul className="list-disc pl-6 text-sm font-semibold">{faltantes.map((f) => <li key={f}>{f}</li>)}</ul>
                </div>
              )}
            </li>
          </Card>
        )
      })}
    </ul>
  )
}

export function DocumentosEvento({ carga }: { carga: Carga }) {
  const resumen = carga.tipo === 'listo' ? resumenCobertura(carga.datos.documentos) : null
  return (
    <section className="grid gap-3" aria-labelledby="titulo-documentos">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="titulo-documentos">Documentos del evento</h2>
        {resumen && (
          <p className="text-sm font-semibold data-[faltantes=true]:text-estado-revision" data-faltantes={resumen.conFaltantes > 0}>{resumen.texto}</p>
        )}
      </div>
      {carga.tipo === 'cargando' && <p className="text-sm text-muted-foreground" aria-busy="true">Cargando documentos…</p>}
      {carga.tipo === 'error' && (
        <Alert variant="destructive" role="alert">No se pudieron cargar los documentos. {carga.motivo}</Alert>
      )}
      {carga.tipo === 'listo' && carga.datos.documentos.length > 0 && <ListaDocumentos documentos={carga.datos.documentos} />}
    </section>
  )
}
