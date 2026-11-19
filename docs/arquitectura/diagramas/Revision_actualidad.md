# Revisión de actualidad de los diagramas

19 de noviembre de 2026. Alcance solicitado: verificar si las figuras publicadas reflejan la implementación actual y si el proyecto puede considerarse terminado. Se inspeccionaron ambos PNG, sus fuentes HTML, la leyenda y el código relacionado. No se modificaron las figuras ni se volvió a exportar sobre los originales.

## Veredicto

Los diagramas son legibles y pasan su verificador de maquetación, pero están desactualizados en contenido. No deben presentarse como descripción exacta de la versión entregada hasta corregir los hallazgos siguientes. Un PASS visual de la entrega D1 no prueba vigencia respecto del código posterior.

## Hallazgos

| Prioridad | Diferencia | Evidencia y corrección necesaria |
|---|---|---|
| Alta | Estados de implementación anteriores al cierre de módulos | El [README](README.md#estado-de-cada-componente) declara autenticación, contexto, auditoría, evaluación, lista y web por implementar, y el generador sin descargar ni medir. Los HTML y PNG conservan lista/auditoría pendientes y generación parcial. Existen sesión y autorización en `consulta/api.py:231`, auditoría en `plataforma/auditoria.py`, lista en `consulta/lista.py` y `lista_escritura.py`, web en `web/src/App.tsx` y resultados del generador en `docs/plataforma/Reporte_evaluacion.md`. Actualizar estados distinguiendo funcionalidad implementada de metas incumplidas. No asignar a los actores humanos una insignia que se interprete como software pendiente. |
| Alta | JEV aparece conectado desde tres puntos sin distinguir el recorrido entregado | Ambos dibujos conectan guardrail, enrutador y herramienta a JEV. El README afirma que la extracción lo usa para fechas. `consulta/config.py:25` selecciona reglas por defecto; `herramientas.py:316` verifica las fechas por reglas y declara que no llama a JEV. El experimento está documentado en `docs/consulta/Experimento_JEV.md`. Rotular las variantes experimentales por separado y retirar la conexión de fechas del flujo vigente. |
| Alta | La lista parece derivarse de la respuesta generada | En el general, `Respuesta → confirmar → Lista → PostgreSQL` omite la propuesta independiente. `consulta/api.py:328` expone `/lista/propuesta`; `lista.py:386` ejecuta extracción sin enrutador ni LLM. Representar acción del usuario, propuesta, confirmación explícita y escritura autorizada, sin depender de una respuesta generativa previa. |
| Media | Citas inválidas llevan directamente a salida controlada | El flujo detallado solo dibuja esa salida. `orquestador.py:223` contempla hasta dos intentos, una regeneración sujeta al presupuesto y publicación parcial de afirmaciones válidas (`:254` en adelante). Añadir las rutas de regeneración, respuesta parcial y abstención; distinguir el máximo de tres herramientas del límite de una regeneración. |
| Media | Falta la frontera efectiva de autenticación y autorización | La flecha del analista entra directamente al guardrail; el contexto aparece pendiente. `api.py:231` comprueba sesión y origen antes de las rutas protegidas, y las escrituras exigen rol analista. Incluir sesión/cookie y autorización, manteniendo la empresa derivada de la sesión. No presentar login fallido o cuerpo HTTP inválido como abstención documental. |
| Media | El estado compartido se describe como un objeto global que todos escriben | El README dice que el rol 4 crea todos sus campos y todos los pasos los leen/escriben. En el código hay sesión, `Contexto`, variables de `consultar`, `Presupuesto` y `_Ejecucion`; no corresponden a ese único objeto. Describir el marco como contexto y datos por solicitud, distinguiendo los datos autenticados de los resultados de cada etapa. |

La auditoría del orquestador ocurre en `finally` (`orquestador.py:490`), también para salidas tempranas. El README ya explica la omisión de esas flechas por legibilidad: puede conservarse como simplificación explícita. Tampoco corresponde afirmar que la lista sea la única escritura del sistema completo, porque existen ingesta y auditoría; es una escritura de negocio que requiere confirmación.

## Comprobaciones realizadas

- Inspección visual de `arquitectura_general.png` y `flujo_consulta.png`: los estados y conexiones antiguos están también en las imágenes publicadas, no solo en sus fuentes.
- Navegador Chromium sobre ambos HTML con `?verificar`: resultado `OK`, sin errores JavaScript.
- Arquitectura general: lienzo medido de 1600 × 1094, igual al declarado.
- Flujo de consulta: lienzo medido de 1600 × 1020, igual al declarado.
- Evidencia temporal: `/tmp/licigt-diagramas-verificacion.json`, `/tmp/licigt-diagramas-verificar.cjs` y capturas `/tmp/licigt-*-revision.png`.
- Los enlaces del anteproyecto apuntan a estos dos PNG y el informe técnico remite a su carpeta: corregir las fuentes y regenerar las imágenes es necesario para que esos documentos muestren el estado vigente. No se verificó el contenido embebido en PDF exportados previamente.

## Estado de cierre del proyecto

La corrección visual de la web está verificada, pero no cierra la entrega completa. Según los documentos disponibles, quedan la presentación propia de 15 minutos, la comprobación de extensión/formato del informe de 10–15 páginas y la nueva demo con sesión y servicios reales. Los cambios visuales siguen sin commit.

Persisten limitaciones medidas: P95 de 32,0 s con un usuario y 37,5 s con cinco frente a la meta de 15 s; 19/23 casos del banco del rol 3 y 11/20 del banco común cumplen. Fidelidad factual, cobertura de requisitos y tiempo de revisión con usuarios figuran sin medir en el README raíz. No son equivalentes a fallos de las pruebas unitarias y no se deben presentar como metas alcanzadas. Las mediciones citadas son las ya registradas; no se repitió la evaluación en esta revisión.

`docs/Pendientes.md` y `Plan_rol_3.md` contienen estados antiguos: dicen que casi todos los cambios del anteproyecto siguen sin aplicar, pero `docs/anteproyecto/Cambios_pendientes.md`, fechado el 19, ya registra la mayoría resueltos. Antes del cierre hay que reconciliar esas listas. Langfuse y un almacén remoto son decisiones diferidas; no se cuentan automáticamente como bloqueos de la demo local.

## Cierre del 19 de noviembre

Los hallazgos de contenido de este informe ya estaban corregidos en las fuentes HTML cuando se escribió; faltaba regenerar las imágenes. Se ejecutó `make diagramas` y ambos PNG se exportaron con verificación de maquetación `OK`: arquitectura general de 1600 × 1134 y flujo de consulta de 1600 × 1128. Las figuras publicadas muestran sesión y autorización, JEV solo como experimento sin conexiones, la propuesta de lista independiente, la regeneración y la publicación parcial. Las listas de `Pendientes.md`, `Plan_rol_3.md` y el aviso al rol 1 quedaron reconciliadas. Lo que sigue abierto son mediciones, decisiones del equipo y la demo con sesión, no contenido desactualizado de las figuras.

## Ampliación del 19 de noviembre

Se añadieron siete figuras (ingesta, recuperación, generación, tres recorridos extremo a extremo y el experimento con JEV). Las cuatro primeras que dejó el agente anterior se rehicieron: tenían notas de relleno, algunas sin respaldo en el código (firma y sello de tiempo del paquete, "la temperatura es cero" y "el prompt no cambia entre reintentos" cuando la regeneración usa temperatura 0,3 y otra semilla, el original guardado antes de extraer) y un orden de extracción incorrecto. Cifras y nombres se tomaron de `pipeline.py`, `pdf.py`, `busqueda.py`, `generacion.py`, `herramientas.py`, `lista_escritura.py`, `Experimento_JEV.md` y `data/plataforma/reporte/20261119T061552Z.md`. `make diagramas` exporta los nueve PNG con verificación `OK`.
