import { useId } from 'react'
import { rutaOriginal } from '../api'
import { rotuloDocumento } from '../cobertura'
import type { MapaTipos } from '../cobertura'
import { agruparPorDocumento, esHttps } from '../estado'
import { mostrarCita } from '../lista'
import type { Fuente } from '../tipos'

const paginas = (f: Fuente) =>
  f.page_end === null || f.page_end === f.page ? `p. ${f.page}` : `pp. ${f.page}–${f.page_end}`

function TarjetaFuente({ f, n, tipos, eventoId }: { f: Fuente; n: number; tipos?: MapaTipos; eventoId?: string }) {
  const id = useId()
  return (
    <article className="fuente" aria-labelledby={id}>
      <h3 id={id} className="fuente__titulo">[{n}] {rotuloDocumento(f.doc_id, tipos)}</h3>
      <dl className="fuente__meta">
        <div><dt>Página</dt><dd>{paginas(f)}</dd></div>
        <div><dt>Versión de ingesta</dt><dd>v{f.version_ingesta}</dd></div>
        <div><dt>Versión oficial</dt><dd>{f.version_oficial ?? 'No indicada'}</dd></div>
        <div><dt>Fragmento</dt><dd className="mono">{f.chunk_id}</dd></div>
      </dl>
      <blockquote className="cita" lang="es">{mostrarCita(f.cita)}</blockquote>
      {eventoId && (
        <p className="fuente__origen">
          <a className="fuente__original" href={rutaOriginal(eventoId, f.doc_id, f.page)} target="_blank" rel="noopener">
            Ver copia archivada, p. {f.page} <span className="oculto-visual">(abre en una pestaña nueva)</span>
          </a>
        </p>
      )}
      {esHttps(f.source) ? (
        <p className="fuente__origen">
          <a href={f.source} target="_blank" rel="noopener noreferrer">
            Publicación en igssgt.org <span className="oculto-visual">(abre en una pestaña nueva)</span>
          </a>
        </p>
      ) : (
        <p className="fuente__origen">Publicación externa no disponible ({f.doc_id})</p>
      )}
    </article>
  )
}

function Contraste({ fuentes, tipos, eventoId }: { fuentes: Fuente[]; tipos?: MapaTipos; eventoId?: string }) {
  const grupos = agruparPorDocumento(fuentes)
  const inicios = grupos.map((_, i) => grupos.slice(0, i).reduce((a, g) => a + g.fuentes.length, 1))
  return (
    <>
      <h2>Fuentes en conflicto</h2>
      <p className="contraste__frase">El sistema no decide cuál está vigente.</p>
      <div className="contraste">
        {grupos.map((g, i) => (
          <ColumnaDocumento key={g.doc_id} doc_id={g.doc_id} fuentes={g.fuentes} inicio={inicios[i]} tipos={tipos} eventoId={eventoId} />
        ))}
      </div>
    </>
  )
}

function ColumnaDocumento({ doc_id, fuentes, inicio, tipos, eventoId }: { doc_id: string; fuentes: Fuente[]; inicio: number; tipos?: MapaTipos; eventoId?: string }) {
  const id = useId()
  return (
    <section className="contraste__columna" aria-labelledby={id}>
      <header>
        <p id={id} className="contraste__doc">{rotuloDocumento(doc_id, tipos)}</p>
        <p className="contraste__version">Versión oficial: {fuentes[0].version_oficial ?? 'No indicada'}</p>
      </header>
      {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={inicio + i} tipos={tipos} eventoId={eventoId} />)}
    </section>
  )
}

interface Props { fuentes: Fuente[]; abstencion: boolean; conflicto: boolean; tipos?: MapaTipos; eventoId?: string }

export function ZonaFuentes({ fuentes, abstencion, conflicto, tipos, eventoId }: Props) {
  if (fuentes.length === 0) {
    return (
      <section className="fuentes">
        <h2>Fuentes</h2>
        <p className="ayuda">Sin fuentes: no se encontró evidencia suficiente.</p>
      </section>
    )
  }
  if (conflicto && new Set(fuentes.map((f) => f.doc_id)).size >= 2) {
    return <section className="fuentes"><Contraste fuentes={fuentes} tipos={tipos} eventoId={eventoId} /></section>
  }
  return (
    <section className="fuentes">
      <h2>{abstencion ? 'Fragmentos recuperados (no respaldan una respuesta)' : `Fuentes (${fuentes.length})`}</h2>
      {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={i + 1} tipos={tipos} eventoId={eventoId} />)}
    </section>
  )
}
