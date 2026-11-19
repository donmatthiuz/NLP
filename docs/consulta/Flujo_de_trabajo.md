# Flujo de trabajo del rol 3

**Estado al 18 de noviembre de 2026.** Se aplica a cada tarea antes de delegar código. Adaptado de un flujo de otro proyecto: se conservaron los cinco porqués, el inventario de impacto, el diseño con visto bueno, los roles separados al implementar y la verificación posterior.

**Qué cambió respecto de la versión del 16 de noviembre:**

- Desde el 18 de noviembre de 2026 el gestor consume los cuatro roles y se trabaja directo en la rama `proyecto`, que los integra (antes, el rol 3 trabajaba en `rol/consulta`). No se trabaja directo en `main`.
- Los implementadores son subagentes Sonnet lanzados por el gestor, y el adversario que audita es un agente Opus. La versión anterior decía Codex u OpenCode para implementar y Kimi para el adversario. Este cambio ya se había practicado; la revisión retrospectiva lo declaró desvío del flujo escrito y el usuario lo aprobó el 18 de noviembre ([Revision_retrospectiva](Revision_retrospectiva.md)).
- Las instrucciones vigentes para agentes están en `AGENTS.md` en la raíz.

## Principio: primero lo que se pide, con base para lo demás

- Primero se cumple lo que exigen el [curso](../anteproyecto/Anteproyecto.md) y el anteproyecto. Lo que no lo exige se difiere.
- Se deja el punto de extensión (una interfaz, un campo opcional, una función con un solo llamador), no la funcionalidad.
- Una pieza se construye en la fase en que se usa, no antes.

Cuatro preguntas para cada elemento propuesto. Si todas las respuestas son "no", se difiere y se anota en [Pendientes](../Pendientes.md):

1. ¿Lo pide el curso, el anteproyecto o la asignación de roles?
2. ¿Lo ejercita algún caso del banco, la demo o una prueba de esta fase?
3. ¿Otro rol o la fase siguiente depende de esto ya?
4. ¿Su ausencia obligaría a rehacer lo demás? Si sí, se deja el gancho mínimo.

## Pasos

1. **Alcance.** Se enuncia qué entrega la tarea y con qué requisito se justifica (sección del curso, del anteproyecto o del plan).
2. **Inventario de impacto.** Se lista qué lee y qué escribe lo que se va a tocar, quién lo llama y qué documentos lo describen. Se usa `grep` y lectura de los contratos y de [Contratos](Contratos.md); no hay grafo de código en este repositorio. Se revisan también los README y `docs/` del módulo vecino.
3. **Cinco porqués.** El agente `five-whys` revisa el cambio propuesto. Cada respuesta cita evidencia del repo (archivo y línea, o commit). Lo que no tiene respuesta se escala al usuario con la pregunta exacta; lo demás no se pregunta.
4. **Diseño y plan.** El gestor presenta qué cambia en código, documentación y pruebas, y qué se difiere. Se espera el visto bueno antes de delegar.
5. **Implementación con roles separados.** Un subagente Sonnet implementa siguiendo un encargo escrito en `docs/<módulo>/delegacion/` (prueba en rojo primero, sin ampliar el alcance). Un agente adversario Opus, de solo lectura, intenta refutar la entrega contra su encargo y las reglas de `AGENTS.md`, con veredicto REFUTADO o NO_REFUTADO. El gestor reproduce los hallazgos graves antes de encargar la corrección y no escribe el código de producción. Las tareas independientes se entregan en paralelo.
6. **Verificación.** Se ejecutan las pruebas del módulo y las de los módulos vecinos que no requieran servicios externos, y lo medido se corre con los servicios reales. Si hay configuración de lint o formato, solo en los archivos tocados. Cada fallo se clasifica como propio o ajeno; solo se arregla lo propio y lo ajeno se anota en el aviso del rol correspondiente. Un resultado se reporta como medido; las metas del anteproyecto no son resultados.
7. **Registro.** Se actualizan [Pendientes](../Pendientes.md), el plan del rol y los avisos, con el commit de cada casilla. Los commits se hacen cuando el usuario lo pide.

## Variantes del flujo

- **Interfaz web.** Se escribe antes un contrato de diseño (`web/DISENO.md`). Los agentes de diseño implementan y el agente `design-ui-finish-gate-reviewer` valida con PASS o HOLD, sin editar. La web no se da por terminada sin la compuerta (F6f dio HOLD y luego PASS; W2 dio PASS el 18 de noviembre).
- **Casos de prueba.** El proponente (`proponente-casos`, en Codex) redacta los casos con la [guía de etiquetado](Guia_de_etiquetado.md), sin ver la implementación. El revisor (`revisor-casos`, en Claude, en sesión aislada) los etiqueta a ciegas o verifica su evidencia. El usuario adjudica los desacuerdos, y esa adjudicación cuenta como segunda revisión declarada.
- **Experimentos de adopción** (JEV en el enrutador, variante LLM, JEV en las fechas). La regla de adopción y la partición desarrollo y prueba se fijan antes de correr. El conjunto de prueba se corre una sola vez y no se ajusta nada mirando sus fallos. Si algo cambia después de ver el resultado, se declara. El veredicto lo da la regla, no la preferencia ([Experimento_JEV](Experimento_JEV.md)).
- **Revisión retrospectiva.** Al cerrar los roles se revisa lo ya hecho con el mismo criterio que lo nuevo: cinco porqués con evidencia, y un veredicto por decisión (bien, mal, mejorable o escalar) con su acción ([Revision_retrospectiva](Revision_retrospectiva.md)).

## Reglas de proceso

- Nunca se ejecuta código propio mediante un objetivo de `make` que arme credenciales (por ejemplo `make importar PYTHON="python3 script.py"`): ese código recibiría la URL de la base con su contraseña. Para trabajar contra la base se usan los objetivos existentes o uno nuevo y explícito en el `Makefile`.
- Los agentes no leen ni copian `keys/`. Las llaves se gestionan con `make key-set` y `make keys-status`.
- Antes de escribir código contra una librería se consulta su documentación actual con Context7.

## Roles

- **Usuario:** da el visto bueno de diseño y decide lo escalado.
- **Gestor (Claude):** inventario, cinco porqués, diseño, encargos, reproducción de los hallazgos del adversario, mediciones y documentación.
- **Implementador (subagente Sonnet):** escribe el código y las pruebas del encargo, sin ampliar el alcance.
- **Adversario (agente Opus):** audita cada entrega sin editar nada.
- **Proponente (Codex) y revisor (Claude):** casos de prueba etiquetados, con modelos de distinta familia.

## Avisos a otros roles

Lo que un rol necesita de otro se escribe en `docs/<módulo>/Avisos_del_rol_<n>.md`, con la opción por defecto si no hay respuesta, para no quedar bloqueado. Mantener esos avisos al día es del gestor, no una tarea del usuario. Los del rol 3:

- [Rol 1](../ingesta/Avisos_del_rol_3.md)
- [Rol 2](../recuperacion/Avisos_del_rol_3.md)
- [Rol 4](../plataforma/Avisos_del_rol_3.md)
