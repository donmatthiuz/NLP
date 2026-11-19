import { useId } from 'react'
import type { ReactNode } from 'react'
import { rutaOriginal } from '../api'
import { rotuloDocumento } from '../cobertura'
import type { MapaTipos } from '../cobertura'
import { agruparPorDocumento, esHttps } from '../estado'
import { mostrarCita } from '../lista'
import type { Fuente } from '../tipos'
import { Card } from './ui/card'

// "p. 8 del PDF (impresa 6)": la página física del PDF manda (el enlace navega a ella);
// la impresa en la hoja se agrega solo si el backend la trae.
export function textoPagina(f: Pick<Fuente, 'page' | 'page_end' | 'printed_page'>): string {
  const pdf = f.page_end === null || f.page_end === f.page ? `p. ${f.page} del PDF` : `pp. ${f.page}–${f.page_end} del PDF`
  return f.printed_page ? `${pdf} (impresa ${f.printed_page})` : pdf
}

// Cita literal: borde de control, fondo muted y 70ch como máximo (DISENO.md, "Tarjeta de fuente").
export const CLASE_CITA = 'max-w-[70ch] rounded-lg border-l-3 border-input bg-muted px-4 py-3 leading-texto wrap-anywhere'

function Dato({ rotulo, children, mono = false }: { rotulo: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="flex min-w-0 flex-wrap content-start gap-x-1">
      <dt className="text-muted-foreground after:content-[':']">{rotulo}</dt>
      <dd className={mono ? 'min-w-0 font-mono wrap-anywhere' : 'min-w-0 font-semibold wrap-anywhere'}>{children}</dd>
    </div>
  )
}

// Metadatos en dos columnas solo si la tarjeta mide 28rem o más (@md): en el contraste lado a lado
// cada tarjeta es angosta y van en una.
function TarjetaFuente({ f, n, tipos, eventoId }: { f: Fuente; n: number; tipos?: MapaTipos; eventoId?: string }) {
  const id = useId()
  return (
    <Card asChild className="@container gap-3 p-4">
      <article aria-labelledby={id}>
        <header className="grid min-w-0 gap-3">
          <h3 id={id} className="wrap-anywhere">[{n}] {rotuloDocumento(f.doc_id, tipos)}</h3>
          <dl className="grid gap-x-4 gap-y-2 text-sm @md:grid-cols-2">
            <Dato rotulo="Página">{textoPagina(f)}</Dato>
            <Dato rotulo="Versión de ingesta">v{f.version_ingesta}</Dato>
            <Dato rotulo="Versión oficial">{f.version_oficial ?? 'No indicada'}</Dato>
            <Dato rotulo="Fragmento" mono>{f.chunk_id}</Dato>
          </dl>
        </header>
        <blockquote className={CLASE_CITA} lang="es">{mostrarCita(f.cita)}</blockquote>
        <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border pt-2 text-sm wrap-anywhere">
          {eventoId && (
            <a className="inline-block py-1 font-semibold" href={rutaOriginal(eventoId, f.doc_id, f.page)} target="_blank" rel="noopener">
              Ver copia archivada, p. {f.page} del PDF <span className="sr-only">(abre en una pestaña nueva)</span>
            </a>
          )}
          {esHttps(f.source) ? (
            <a className="inline-block py-1" href={f.source} target="_blank" rel="noopener noreferrer">
              Publicación en igssgt.org <span className="sr-only">(abre en una pestaña nueva)</span>
            </a>
          ) : (
            <p className="py-1 text-muted-foreground">Publicación externa no disponible ({f.doc_id})</p>
          )}
        </div>
      </article>
    </Card>
  )
}

function Contraste({ fuentes, tipos, eventoId }: { fuentes: Fuente[]; tipos?: MapaTipos; eventoId?: string }) {
  const grupos = agruparPorDocumento(fuentes)
  const inicios = grupos.map((_, i) => grupos.slice(0, i).reduce((a, g) => a + g.fuentes.length, 1))
  return (
    <>
      <div className="grid gap-1">
        <h2>Fuentes en conflicto</h2>
        <p className="font-semibold">El sistema no decide cuál está vigente.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-[repeat(auto-fit,minmax(18rem,1fr))]">
        {grupos.map((g, i) => (
          <ColumnaDocumento key={g.doc_id} doc_id={g.doc_id} fuentes={g.fuentes} inicio={inicios[i]} tipos={tipos} eventoId={eventoId} />
        ))}
      </div>
    </>
  )
}

// Las columnas comparten variante y peso: ninguna se rotula, atenúa ni ordena como vigente.
function ColumnaDocumento({ doc_id, fuentes, inicio, tipos, eventoId }: { doc_id: string; fuentes: Fuente[]; inicio: number; tipos?: MapaTipos; eventoId?: string }) {
  const id = useId()
  return (
    <Card asChild className="content-start gap-3 border-2 border-input bg-background p-3">
      <section aria-labelledby={id}>
        <header className="grid gap-1 border-b border-border px-1 pb-3">
          <p id={id} className="font-semibold wrap-anywhere">{rotuloDocumento(doc_id, tipos)}</p>
          <p className="text-sm text-muted-foreground">Versión oficial: {fuentes[0].version_oficial ?? 'No indicada'}</p>
        </header>
        {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={inicio + i} tipos={tipos} eventoId={eventoId} />)}
      </section>
    </Card>
  )
}

interface Props { fuentes: Fuente[]; abstencion: boolean; conflicto: boolean; tipos?: MapaTipos; eventoId?: string }

export function ZonaFuentes({ fuentes, abstencion, conflicto, tipos, eventoId }: Props) {
  if (fuentes.length === 0) {
    return (
      <section className="grid gap-2">
        <h2>Fuentes</h2>
        <p className="text-sm text-muted-foreground">Sin fuentes: no se encontró evidencia suficiente.</p>
      </section>
    )
  }
  if (conflicto && new Set(fuentes.map((f) => f.doc_id)).size >= 2) {
    return <section className="grid gap-4"><Contraste fuentes={fuentes} tipos={tipos} eventoId={eventoId} /></section>
  }
  return (
    <section className="grid gap-4">
      <h2>{abstencion ? 'Fragmentos recuperados (no respaldan una respuesta)' : `Fuentes (${fuentes.length})`}</h2>
      {fuentes.map((f, i) => <TarjetaFuente key={f.chunk_id + i} f={f} n={i + 1} tipos={tipos} eventoId={eventoId} />)}
    </section>
  )
}
