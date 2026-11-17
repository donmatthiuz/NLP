import { forwardRef } from 'react'
import { ROTULOS, estadoDe, motivoRevision } from '../estado'
import type { RespuestaEstructurada } from '../tipos'
import { IconoCobertura, IconoEstado } from './Iconos'

const HERRAMIENTAS = {
  buscar_documentos: 'Búsqueda en documentos',
  extraer_requisitos: 'Extracción de requisitos',
  comparar_versiones: 'Comparación de versiones',
}

const ROTULOS_AVISO: Record<string, string> = {
  cobertura_incompleta: 'Cobertura incompleta',
  evento_con_modificaciones: 'El evento tiene modificaciones',
  candidatas_sin_verificar: 'Fechas sin verificar',
  alerta_desconocida: 'Alerta no reconocida',
}

const rotuloAviso = (w: string) => ROTULOS_AVISO[w.split(':')[0]] ?? 'Aviso del sistema'

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
    <section className="resultado" data-estado={estado} aria-label="Resultado">
      <header className="resultado__cabecera">
        <IconoEstado estado={estado} />
        <h2 ref={rotuloRef} tabIndex={-1}>{ROTULOS[estado]}</h2>
      </header>
      {motivo && (
        <p className="banda-revision">
          {estado !== 'revision' && <strong>Requiere revisión humana. </strong>}{motivo}
        </p>
      )}
      <div className="resultado__cuerpo">
        {aclaracion && <p className="ayuda">Su pregunta: «{pregunta}»</p>}
        <p className="respuesta-texto">{aclaracion ? r.clarification_question : r.answer}</p>
        {estado === 'abstencion' && (
          <p className="ayuda">Que no aparezca en los documentos cargados no prueba que no exista en el expediente.</p>
        )}
        {aclaracion ? (
          <button type="button" className="boton boton--secundario" onClick={alEscribirAclaracion}>Escribir la aclaración</button>
        ) : (
          <dl className="metadatos">
            <div><dt>Evento</dt><dd>{r.evento_id}</dd></div>
            <div><dt>Herramienta</dt><dd>{r.tool_used ? HERRAMIENTAS[r.tool_used] : 'Ninguna'}</dd></div>
            <div>
              <dt>Cobertura</dt>
              <dd>
                {r.coverage_status === 'parcial' ? 'parcial' : 'sin faltantes detectados'}
                {r.coverage_status !== 'parcial' && <span className="ayuda"> (no certifica que el expediente esté completo)</span>}
              </dd>
            </div>
          </dl>
        )}
        <div className="avisos">
          {r.coverage_status === 'parcial' && !aclaracion && (
            <p className="aviso-cobertura">
              <IconoCobertura />
              <span>Cobertura parcial: hay páginas o documentos del evento que no están indexados. La respuesta puede estar incompleta.</span>
            </p>
          )}
          {r.warnings.length > 0 && (
            <ul className="avisos__lista">
              {r.warnings.map((w, i) => (
                <li key={i}>
                  <strong>{rotuloAviso(w)}</strong>
                  <span className="mono">{w}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
})
