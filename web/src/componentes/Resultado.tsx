import { forwardRef } from 'react'
import { ROTULOS, estadoDe, motivoRevision } from '../estado'
import type { RespuestaEstructurada } from '../tipos'
import { IconoCobertura, IconoEstado } from './Iconos'
import { Alert, AlertDescription } from './ui/alert'
import { Button } from './ui/button'
import { Card } from './ui/card'

const HERRAMIENTAS = {
  buscar_documentos: 'Búsqueda en documentos',
  extraer_requisitos: 'Extracción de requisitos',
  comparar_versiones: 'Comparación de versiones',
}

const ROTULOS_AVISO: Record<string, string> = {
  cobertura_incompleta: 'Cobertura incompleta',
  evento_con_modificaciones: 'El evento tiene modificaciones',
  fechas_no_verificadas: 'Fechas sin verificar',
  fecha_ambigua: 'Fecha ambigua: requiere revisión',
  alerta_desconocida: 'Alerta no reconocida',
  afirmaciones_descartadas: 'Se omitieron afirmaciones que no pasaron la validación de citas',
}

const rotuloAviso = (w: string) => ROTULOS_AVISO[w.split(':')[0]] ?? 'Aviso del sistema'

// data-estado es el único gancho de estilo (DISENO.md, "Cómo se distinguen sin depender del color"):
// cada estado tiene su estilo de borde además del color, y la cabecera toma el fondo del estado.
const PANEL = [
  'group/resultado gap-0 py-0 border-2 forced-colors:border-[CanvasText]',
  'data-[estado=respuesta]:border-y-0 data-[estado=respuesta]:border-r-0 data-[estado=respuesta]:border-l-4 data-[estado=respuesta]:border-estado-respuesta',
  'data-[estado=abstencion]:border-dashed data-[estado=abstencion]:border-estado-abstencion',
  'data-[estado=revision]:border-solid data-[estado=revision]:border-estado-revision',
  'data-[estado=aclaracion]:border-dotted data-[estado=aclaracion]:border-estado-aclaracion',
].join(' ')

const CABECERA = [
  'flex items-center gap-2 px-4 py-3',
  'group-data-[estado=respuesta]/resultado:bg-estado-respuesta-fondo group-data-[estado=respuesta]/resultado:text-estado-respuesta',
  'group-data-[estado=abstencion]/resultado:bg-estado-abstencion-fondo group-data-[estado=abstencion]/resultado:text-estado-abstencion',
  'group-data-[estado=revision]/resultado:bg-estado-revision-fondo group-data-[estado=revision]/resultado:text-estado-revision',
  'group-data-[estado=aclaracion]/resultado:bg-estado-aclaracion-fondo group-data-[estado=aclaracion]/resultado:text-estado-aclaracion',
].join(' ')

interface Props {
  respuesta: RespuestaEstructurada
  pregunta: string
  alEscribirAclaracion: () => void
}

export const Resultado = forwardRef<HTMLHeadingElement, Props>(function Resultado(
  { respuesta: r, pregunta, alEscribirAclaracion }, rotuloRef,
) {
  const estado = estadoDe(r)
  const aclaracion = estado === 'aclaracion'
  const motivo = motivoRevision(r)
  return (
    <Card asChild className={PANEL}>
      <section data-estado={estado} aria-label="Resultado">
        <header className={CABECERA}>
          <IconoEstado estado={estado} />
          <h2 ref={rotuloRef} tabIndex={-1}>{ROTULOS[estado]}</h2>
        </header>
        {motivo && (
          <p className="border-b-2 border-estado-revision bg-estado-revision-fondo px-4 py-3 font-semibold text-foreground forced-colors:border-[CanvasText]">
            {estado !== 'revision' && <strong>Requiere revisión humana. </strong>}{motivo}
          </p>
        )}
        <div className="grid gap-4 p-4">
          {aclaracion && <p className="text-sm text-muted-foreground">Su pregunta: «{pregunta}»</p>}
          <p className="max-w-[70ch] text-lg whitespace-pre-line wrap-anywhere">{aclaracion ? r.clarification_question : r.answer}</p>
          {estado === 'abstencion' && (
            <p className="text-sm text-muted-foreground">Que no aparezca en los documentos cargados no prueba que no exista en el expediente.</p>
          )}
          {aclaracion ? (
            <Button type="button" variant="outline" className="justify-self-start" onClick={alEscribirAclaracion}>Escribir la aclaración</Button>
          ) : (
            <dl className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border pt-3 text-sm">
              <div className="flex flex-wrap gap-x-1">
                <dt className="text-muted-foreground after:content-[':']">Evento</dt><dd className="font-semibold wrap-anywhere">{r.evento_id}</dd>
              </div>
              <div className="flex flex-wrap gap-x-1">
                <dt className="text-muted-foreground after:content-[':']">Herramienta</dt>
                <dd className="font-semibold">{r.tool_used ? HERRAMIENTAS[r.tool_used] : 'Ninguna'}</dd>
              </div>
              <div className="flex flex-wrap gap-x-1">
                <dt className="text-muted-foreground after:content-[':']">Cobertura</dt>
                <dd className="font-semibold">
                  {r.coverage_status === 'parcial' ? 'parcial' : 'sin faltantes detectados'}
                  {r.coverage_status !== 'parcial' && <span className="font-normal text-muted-foreground"> (no certifica que el expediente esté completo)</span>}
                </dd>
              </div>
            </dl>
          )}
          <div className="grid gap-3 empty:hidden">
            {r.coverage_status === 'parcial' && !aclaracion && (
              <Alert variant="revision">
                <IconoCobertura />
                <AlertDescription>Cobertura parcial: hay páginas o documentos del evento que no están indexados. La respuesta puede estar incompleta.</AlertDescription>
              </Alert>
            )}
            {r.warnings.length > 0 && (
              <ul className="grid gap-2">
                {r.warnings.map((w, i) => (
                  <li key={i} className="grid gap-1 border-l-3 border-border pl-3">
                    <strong>{rotuloAviso(w)}</strong>
                    <span className="font-mono text-sm text-muted-foreground wrap-anywhere">{w}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>
    </Card>
  )
})
