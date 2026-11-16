# Flujo de trabajo del rol 3

**Estado al 16 de noviembre de 2026.** Se aplica a cada tarea de [Plan_rol_3](Plan_rol_3.md) antes de delegar código. Adaptado de un flujo de otro proyecto: se conservaron los cinco porqués, el inventario de impacto, el diseño con visto bueno, los roles separados al implementar y la verificación posterior.

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
5. **Implementación con roles separados.** Un agente (Codex u OpenCode) implementa siguiendo un encargo escrito en `docs/consulta/delegacion/`. El gestor revisa por separado e intenta refutarlo contra el diseño; corrige o lo devuelve.
6. **Verificación.** Se ejecutan las pruebas del módulo y las de los módulos vecinos que no requieran servicios externos. Si hay configuración de lint o formato, solo en los archivos tocados. Cada fallo se clasifica como propio o ajeno; solo se arregla lo propio y lo ajeno se anota en el aviso del rol correspondiente.
7. **Registro.** Se actualizan [Pendientes](../Pendientes.md) y el plan. Los commits se hacen cuando el usuario lo pide.

## Roles

- **Usuario:** da el visto bueno de diseño y decide lo escalado.
- **Gestor (Claude):** inventario, cinco porqués, diseño, encargos, auditoría y corrección.
- **Implementador (Codex u OpenCode):** escribe el código y las pruebas del encargo, sin ampliar el alcance.

## Avisos a otros roles

Lo que el rol 3 necesita de otro rol se escribe en `docs/<módulo>/Avisos_del_rol_3.md`, con la opción por defecto si no hay respuesta, para no quedar bloqueado:

- [Rol 1](../ingesta/Avisos_del_rol_3.md)
- [Rol 2](../recuperacion/Avisos_del_rol_3.md)
- [Rol 4](../plataforma/Avisos_del_rol_3.md)
