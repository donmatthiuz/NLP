# Verificación de W3

19 de noviembre de 2026. Diseño aprobado en [W3](W3_refinamiento_visual.md), ejecución según [plan](W3_plan.md). Cambios locales en `proyecto`, sin commit.

## Cambios y revisión

- `design-ux-architect`: selectores y primitivas adaptables, tema compacto, transición de controles de 150 ms y apertura del diálogo de 160 ms/4 px con movimiento reducido.
- `design-ui-designer`: cabecera e inventario compactos, consulta destacada, metadatos agrupados, ayudas breves y radios de dimensiones constantes.
- `design-visual-storyteller`: favicon SVG local y actualización del contrato visual.
- La primera captura móvil mostró recorte de «Comparación con revisión humana» y metadatos con demasiadas líneas. Se abrevió el selector a «Comparación», se pusieron los metadatos en línea cuando caben y se conservaron como `sr-only` los rótulos redundantes del inventario. Todos los valores documentales siguen visibles. El gestor sincronizó el contrato tras esa corrección.

## Resultados medidos

| Comprobación | Resultado |
|---|---|
| `pnpm --dir web test` | 80 pruebas aprobadas, seis archivos |
| `pnpm --dir web build` | TypeScript y Vite aprobados |
| `make test-consulta` | OK: 667 pruebas ejecutadas; 18 omitidas y un fallo esperado |
| Matriz de navegador | 36 vistas: inicio y cinco ejemplos, claro/oscuro, 320/768/1366 px |
| Desbordamiento horizontal | Ninguno en las 36 vistas ni en los seis flujos de lista |
| Errores JavaScript | Ninguno en la matriz |
| Lista y confirmación | Seis recorridos: proponer, abrir, cancelar, confirmar, cambiar estado y descartar |
| Foco del diálogo | Dentro al abrir; vuelve al botón de origen al cancelar en seis recorridos |
| Radios | Mismas posiciones y dimensiones antes/después de seleccionar en seis recorridos |
| Movimiento reducido | `animation-name: none` en seis recorridos |
| Favicon | HTTP 200, tipo `image/svg+xml` |

Las pruebas de consulta se detuvieron en la primera prueba HTTP dentro del sandbox; se interrumpió esa ejecución y se repitió el mismo objetivo fuera del sandbox, donde completó en 5,651 s. No se modificó código para resolverlo. Context7 rechazó la credencial; el uso de documentación oficial alternativa está registrado en el diseño W3.

## Evidencia y límites

Capturas y scripts locales en `/tmp/licigt-w3/`: `capture.cjs`, `report.json`, capturas por estado/tema/ancho y `test-consulta.log`. Son artefactos temporales, no versionados.

La matriz usa Chromium y los datos del modo ejemplos. El guardado de la lista se ejercitó solo sobre ese adaptador en memoria. No se consultó un LLM ni se modificó una lista real. No se declara validación en otros navegadores ni con la API de producción.

## Compuerta independiente

**PASS**, emitido por `design-ui-finish-gate-reviewer` tras inspeccionar capturas finales y ejecutar una comprobación independiente en vivo en los seis tamaños/temas.

- Selector de comparación completo a 320 px; evidencia y advertencias visibles; fuentes en conflicto de igual peso.
- Aclaración devuelve foco a la pregunta; diálogo enfoca el título, retiene tabulación y devuelve foco al cancelar.
- Flechas seleccionan «Preparado» y muestran «Guardar cambio» con alturas de 44 px y bordes de 2 px constantes. El sondeo inicial enviaba keydown/keyup sin demora: movía el foco sin seleccionar; la pulsación de 100 ms verificó selección en seis recorridos y el gestor reprodujo ambos resultados. No se modificó el comportamiento de Radix.
- Movimiento reducido sin animación y transición de 0 s. Sin errores JavaScript ni desbordamiento.

Evidencia independiente temporal: `/tmp/licigt-w3/reviewer-live.cjs`, `reviewer-live.json` y `reviewer-dialog-*.png`. No certifica accesibilidad WCAG completa ni lectores de pantalla. No se recalculó el contraste de la paleta existente ni se midió densidad frente a W2. Sin bloqueantes visuales pendientes dentro de W3.
