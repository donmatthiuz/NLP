# Plan de implementación W3

**Objetivo:** aplicar el [diseño W3 aprobado](W3_refinamiento_visual.md) mediante los agentes de diseño y verificarlo con una compuerta independiente.

**Arquitectura:** conservar contratos y comportamiento; reorganizar JSX y utilidades existentes. Los agentes tienen archivos exclusivos; el gestor integra, documenta y verifica. React, Vite, Tailwind v4 y shadcn/ui actuales, sin dependencias nuevas.

## Restricciones y foco de revisión

- Rama `proyecto`, sin commits, push ni cambios en backend o secretos.
- Evidencia y advertencias completas; guardado únicamente al confirmar. Paletas actuales, 44 px en controles, foco visible y movimiento reducido.
- Revisar identificadores largos a 320 px, selectores de ejemplo largos, cambios de radio sin saltos, diálogo con teclado y todas las advertencias en los cinco escenarios.
- Cambios de presentación: usar las pruebas existentes y validación en navegador; no añadir pruebas que simplemente repitan clases CSS.

## Tareas

- [x] **UX Architect:** `ui/native-select.tsx`, `ui/card.tsx`, `ui/button.tsx`, `estilos/tema.css`, `Tema.tsx`, `Confirmacion.tsx`. Mantener las mismas props y semántica; selectores contenidos, transición 150 ms, diálogo con animación 160 ms/4 px y movimiento reducido. Verificar compilación y dimensiones/foco en navegador.
- [x] **UI Designer:** `App.tsx`, `DocumentosEvento.tsx`, `ListaVerificacion.tsx`, `Fuentes.tsx` y la etiqueta de comparación en `ejemplos/index.ts`. Compactar cabecera e inventario, organizar metadatos de fuentes y lista, agrupar acciones, acortar ayudas aprobadas y mantener borde 2 px en radios. Mantener todos los datos, nombres accesibles y funciones actuales. Verificar pruebas web existentes.
- [x] **Visual Storyteller:** `web/index.html`, `web/public/favicon.svg`, `web/DISENO.md`. Crear favicon de documento grafito/blanco sin letras ni símbolo de aprobación; actualizar contrato al diseño aprobado y coordinar detalles finales con implementadores. Verificar recurso local y documentación consistente.
- [x] **Gestor:** ejecutar `pnpm --dir web test`, `pnpm --dir web build`, `git diff --check`; capturar estados inicial y cinco ejemplos, lista y diálogo, claro/oscuro a 320, 768 y 1366 px. Verificar teclado, reduced motion y desbordamiento; documentar evidencia.
- [x] **Finish-gate reviewer:** leer `.agentes/design-ui-finish-gate-reviewer.md`; revisar implementación en vivo, capturas y contrato; emitir PASS/HOLD sin editar producto. Reproducir y corregir hallazgos antes del cierre.
- [x] **Gestor:** actualizar registro W3 y plan del rol 3 con resultados medidos y limitaciones. Mantener cambios sin commit.

Resultados medidos y límites en [W3_verificacion](W3_verificacion.md). Compuerta independiente: PASS.
