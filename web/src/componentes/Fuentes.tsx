import { useId } from 'react'
import { agruparPorDocumento, esHttps } from '../estado'
import type { Fuente } from '../tipos'

const paginas = (f: Fuente) =>
  f.page_end === null || f.page_end === f.page ? `p. ${f.page}` : `pp. ${f.page}–${f.page_end}`

function TarjetaFuente({ f, n }: { f: Fuente; n: number }) {
  const id = useId()
  return (
    <article className="fuente" aria-labelledby={id}>
      <h3 id={id} className="fuente__titulo">[{n}] {f.doc_id}</h3>
      <dl className="fuente__meta">
        <div><dt>Página</dt><dd>{paginas(f)}</dd></div>
        <div><dt>Versión de ingesta</dt><dd>v{f.version_ingesta}</dd></div>
        <div><dt>Versión oficial</dt><dd>{f.version_oficial ?? 'No indicada'}</dd></div>
        <div><dt>Fragmento</dt><dd className="mono">{f.chunk_id}</dd></div>
      </dl>
      <blockquote className="cita" lang="es">{f.cita}</blockquote>
      {esHttps(f.source) ? (
        <p className="fuente__origen">
          <a href={f.source} target="_blank" rel="noopener noreferrer">
            Abrir documento original <span className="oculto-visual">(página {f.page}), abre en una pestaña nueva</span>
          </a>{' '}
          <span aria-hidden="true">(página {f.page})</span>
        </p>
      ) : (
        <p className="fuente__origen">Original no disponible en línea ({f.doc_id})</p>
      )}
    </article>
  )
}

function Contraste({ fuentes }: { fuentes: Fuente[] }) {
  const grupos = agruparPorDocumento(fuentes)
  const inicios = grupos.map((_, i) => grupos.slice(0, i).reduce((a, g) => a + g.fuentes.length, 1))
  return (
    <>
      <h2>Fuentes en conflicto</h2>
      <p className="contraste__frase">El sistema no decide cuál está vigente.</p>
      <div className="contraste">
        {grupos.map((g, i) => (
          <ColumnaDocumento key={g.doc_id} doc_id={g.doc_id} fuentes={g.fuentes} inicio={inicios[i]} />
        ))}
      </div>
    </>
  )
}

function ColumnaDocumento({ doc_id, fuentes, inicio }: { doc_id: string; fuentes: Fuente[]; inicio: number }) {
  const id = useId()
  return (
    <section className="contraste__columna" aria-labelledby={id}>
      <header>
        <p id={id} className="contraste__doc">{doc_id}</p>
        <p className="contraste__version">Versión oficial: {fuentes[0].version_oficial ?? 'No indicada'}</p>
      </header>
      {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={inicio + i} />)}
    </section>
  )
}

interface Props { fuentes: Fuente[]; abstencion: boolean; conflicto: boolean }

export function ZonaFuentes({ fuentes, abstencion, conflicto }: Props) {
  if (fuentes.length === 0) {
    return (
      <section className="fuentes">
        <h2>Fuentes</h2>
        <p className="ayuda">Sin fuentes: no se encontró evidencia suficiente.</p>
      </section>
    )
  }
  if (conflicto && new Set(fuentes.map((f) => f.doc_id)).size >= 2) {
    return <section className="fuentes"><Contraste fuentes={fuentes} /></section>
  }
  return (
    <section className="fuentes">
      <h2>{abstencion ? 'Fragmentos recuperados (no respaldan una respuesta)' : `Fuentes (${fuentes.length})`}</h2>
      {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={i + 1} />)}
    </section>
  )
}
